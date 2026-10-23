from datetime import datetime,timedelta
from typing import Literal,Optional
from fastapi import APIRouter,Request,HTTPException,Query
from pydantic import BaseModel,Field,ConfigDict,field_validator
import anyio
from .ai import JourneyInput,active_network,network_snapshot
from ..services.forecast_service import forecast
from ..services.journey_profiles import illustrative_predictions
from ..services.ai_journey_service import AIJourneyService,IST
from ..services.showcase_service import what_if
from ..services.assistant_service import interpret
from ..services.evaluation_service import evaluation
from ..services.bus_state_service import BusStateService
from ..utils.time_utils import utc_now

router=APIRouter()

def snapshot(request):
    return network_snapshot(request)

class WhatIfInput(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    journey:JourneyInput
    route_id:str=Field(min_length=1,max_length=100)
    traffic_factor:float=Field(default=1,ge=1,le=3)
    demand_factor:float=Field(default=1,ge=.5,le=2)
    delay_minutes:float=Field(default=0,ge=0,le=60)
    roadblock:bool=False

@router.post('/api/ai/what-if')
async def preview(body:WhatIfInput,request:Request):
    gtfs,store,events=snapshot(request)
    local=body.journey.departure_time.astimezone(IST)
    try:return await anyio.to_thread.run_sync(lambda:what_if(gtfs,store,events,body,illustrative_predictions(forecast(local.hour,local.minute))))
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

class AssistantInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    text:str=Field(min_length=1,max_length=500)
    departure_time:Optional[datetime]=None
    @field_validator('departure_time')
    @classmethod
    def timezone(cls,value):
        if value is not None and value.tzinfo is None:raise ValueError('Timezone required')
        return value

@router.post('/api/assistant/interpret')
def assistant(body:AssistantInput):
    from .synthetic import dataset
    _,stops,_,_=dataset()
    return interpret(body.text,stops,body.departure_time)

@router.get('/api/models/evaluation')
def model_evaluation(model:Literal['crowd','eta']='crowd'):
    try:return evaluation(model)
    except (ImportError,OSError,ValueError,RuntimeError,KeyError) as exc:raise HTTPException(503,'Held-out evaluation unavailable; verify model artifacts and dependencies. '+str(exc)) from exc

@router.get('/api/twin')
async def twin(request:Request,boarding_stop:Optional[str]=Query(default=None,max_length=100)):
    gtfs,store,events=snapshot(request);now=utc_now();clock=now.astimezone(IST)
    if boarding_stop is not None and boarding_stop not in gtfs.stops:raise HTTPException(422,'Unknown boarding stop')
    # No extrapolation of synthetic histories outside their supported service clock.
    predictions=await anyio.to_thread.run_sync(lambda:forecast(clock.hour,clock.minute)) if 6<=clock.hour<=21 else None
    def compute():
        rows=[]
        for bus in store.list(True):
            fresh=bus.status!='STALE' and 0<=(now-bus.timestamp).total_seconds()<store.stale_seconds
            occupancy=eta=boarding=None
            prediction_source=None
            seq=[r['stop_id'] for r in gtfs.trip_stops.get(bus.trip_id,[])]
            if fresh and predictions and bus.route_verified and bus.current_stop_id in seq:
                target=bus.next_stop_id
                one=BusStateService(store.stale_seconds);one.buses={bus.bus_id:bus}
                service=AIJourneyService(gtfs,one,events)
                ready=clock.hour*60+clock.minute+clock.second/60
                if target in seq:
                    value=service.live_arrival(bus.route_id,seq,seq.index(target),predictions,ready,clock.date())
                    if value:eta=max(0,value[0]-ready)
                    occupancy=predictions['crowd'].get(target)
                if boarding_stop in seq:
                    value=service.live_arrival(bus.route_id,seq,seq.index(boarding_stop),predictions,ready,clock.date())
                    if value:boarding=max(0,value[0]-ready)
                prediction_source=predictions['mode']
            rows.append(dict(bus_id=bus.bus_id,route_id=bus.route_id,trip_id=bus.trip_id,source=bus.source,timestamp=bus.timestamp.isoformat(),status=bus.status,tracking_status='FRESH' if fresh else 'STALE',speed_kmh=round(bus.speed*3.6,1) if bus.speed is not None and fresh else None,next_stop_id=bus.next_stop_id,next_stop_name=gtfs.stops.get(bus.next_stop_id,{}).get('stop_name'),occupancy_ratio=round(occupancy,3) if occupancy is not None else None,next_stop_eta_minutes=round(eta,2) if eta is not None else None,boarding_eta_minutes=round(boarding,2) if boarding is not None else None,simulation_delay_minutes=round(bus.simulation_delay_seconds/60,2) if bus.source=='SIMULATOR' and bus.simulation_delay_seconds is not None else None,prediction_source=prediction_source))
        return dict(as_of=now.isoformat(),data_source='SYNTHETIC_NETWORK',vehicles=rows,stale_seconds=store.stale_seconds,occupancy_source='Synthetic stop occupancy replay proxy, not a vehicle passenger sensor',eta_source='Fresh GPS remaining-segment fraction × synthetic travel forecast; null if stale, blocked, unavailable or outside 06:00–21:59 IST',boarding_stop_id=boarding_stop)
    return await anyio.to_thread.run_sync(compute)
