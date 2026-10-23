"""Integrated planning and forecast APIs; legacy endpoints remain unchanged."""
from datetime import datetime,timedelta,timezone
from typing import Literal,Optional
from uuid import uuid4
from fastapi import APIRouter,Request,HTTPException
from pydantic import BaseModel,Field,ConfigDict,model_validator
from ..config import ROOT
from ..services.forecast_service import forecast,get_bundle
from ..services.ai_journey_service import AIJourneyService
from ..services.journey_profiles import illustrative_predictions
from ..schemas.network_event import NetworkEvent
from ..utils.time_utils import utc_now

router=APIRouter()

class JourneyInput(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    origin: Optional[str]=Field(default=None,min_length=1,max_length=100)
    destination: str=Field(min_length=1,max_length=100)
    departure_time: datetime
    latitude: Optional[float]=Field(default=None,ge=-90,le=90)
    longitude: Optional[float]=Field(default=None,ge=-180,le=180)
    walking_radius: float=Field(default=1000,gt=0,le=5000)
    transfer_walk_radius: float=Field(default=500,ge=0,le=1000)
    transfer_buffer: float=Field(default=5,ge=2,le=30)
    max_transfers: int=Field(default=2,ge=0,le=2)
    preference: Literal['faster','less_crowd','less_delay','fewer_transfers','most_reliable']='faster'
    arrival_deadline: Optional[datetime]=None
    max_wait_minutes: Optional[float]=Field(default=None,ge=0,le=180)
    secondary_preferences: list[Literal['faster','less_crowd','fewer_transfers','most_reliable']]=Field(default_factory=list,max_length=3)
    @model_validator(mode='after')
    def validate_input(self):
        if self.departure_time.tzinfo is None:raise ValueError('departure_time requires a timezone')
        if self.arrival_deadline is not None and (self.arrival_deadline.tzinfo is None or self.arrival_deadline<self.departure_time):raise ValueError('arrival_deadline requires a timezone and must follow departure')
        if (self.latitude is None)!=(self.longitude is None):raise ValueError('Supply both latitude and longitude')
        if self.origin is None and self.latitude is None:raise ValueError('Supply origin stop or coordinates')
        if self.origin is not None and self.latitude is not None:raise ValueError('Choose either origin stop or coordinates')
        return self


def active_network(request):
    from .synthetic import dataset
    _,stops,_,_=dataset();gtfs=getattr(request.app.state,'ai_gtfs',request.app.state.gtfs)
    expected={s['stop_id']:(float(s['stop_lat']),float(s['stop_lon'])) for s in stops}
    if not gtfs.loaded or set(gtfs.stops)!=set(expected) or not {'SYN_A','SYN_B','SYN_C'}.issubset(gtfs.routes):
        raise HTTPException(409,'AI planner requires the synthetic network. Restart with GTFS_DIR=datasets/synthetic_chennai.')
    if any((gtfs.stops[s]['latitude'],gtfs.stops[s]['longitude'])!=v for s,v in expected.items()):raise HTTPException(409,'Active stop geometry differs from the synthetic training network')
    # Verify exact ordered patterns, not just route names and dimensions.
    import json
    manifest=json.loads((ROOT/'datasets/synthetic_chennai/manifest.json').read_text())
    for route in manifest['routes']:
        for reverse in (False,True):
            rid=route['route_id']+('_R' if reverse else '')
            seq=route['stops'][::-1] if reverse else route['stops']
            if rid not in gtfs.route_trips or any([r['stop_id'] for r in gtfs.trip_stops[t]]!=seq for t in gtfs.route_trips[rid]):raise HTTPException(409,'Active trip graph differs from synthetic model mapping')
    return gtfs

def network_snapshot(request):
    gtfs=active_network(request)
    isolated=hasattr(request.app.state,'ai_gtfs')
    source=request.app.state.ai_store if isolated else request.app.state.store
    event_service=request.app.state.ai_events if isolated else request.app.state.events
    if not isolated:request.app.state.gps.refresh_stale()
    event_service.expire()
    from ..services.bus_state_service import BusStateService
    store=BusStateService(source.stale_seconds)
    store.buses=dict(source.buses)
    return gtfs,store,[e.model_dump(mode='python') for e in event_service.list()]

@router.post('/api/ai/journeys')
async def plan(body:JourneyInput,request:Request):
    gtfs,store,events=network_snapshot(request)
    local=body.departure_time.astimezone(timezone(timedelta(hours=5,minutes=30)))
    import anyio
    from ..services.showcase_service import enrich
    try:return await anyio.to_thread.run_sync(lambda: enrich(AIJourneyService(gtfs,store,events).search(body,illustrative_predictions(forecast(local.hour,local.minute))),body.preference))
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

class ForecastInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    hour:int=Field(default=8,ge=6,le=21)
    minute:int=Field(default=0,ge=0,le=59)
    route_id:Optional[str]=None
    stop_id:Optional[str]=None

@router.post('/api/predict/eta')
def eta(body:ForecastInput):
    data=forecast(body.hour,body.minute)
    rows=[dict(route_id=r,from_stop_id=a,to_stop_id=b,travel_minutes=round(v,3),travel_seconds=round(v*60,2)) for (r,a,b),v in data['eta'].items() if body.route_id is None or r==body.route_id]
    if not rows:raise HTTPException(422,'Route is not in the synthetic segment mapping')
    return dict(data_source='SYNTHETIC',model=data['eta_model'],mode=data['mode'],fallback_reason=data['fallback_reason'],history_source=data['history_source'],prediction_horizon_minutes=15 if data['horizons'] else None,segments=rows,route_travel_minutes=round(sum(r['travel_minutes'] for r in rows),3) if body.route_id else None,scope='Next-bin segment duration, before scenario effects; aggregated route duration is a planning assumption, not a calibrated long-horizon forecast')

@router.post('/api/predict/crowd')
def crowd(body:ForecastInput):
    data=forecast(body.hour,body.minute)
    rows=[dict(stop_id=s,occupancy_ratio=round(v,4),crowd_level='HIGH' if v>=.7 else 'MEDIUM' if v>=.4 else 'LOW') for s,v in data['crowd'].items() if body.stop_id is None or s==body.stop_id]
    if not rows:raise HTTPException(422,'Stop is not in the synthetic crowd mapping')
    return dict(data_source='SYNTHETIC',model=data['crowd_model'],mode=data['mode'],fallback_reason=data['fallback_reason'],history_source=data['history_source'],prediction_horizon_minutes=5 if data['horizons'] else None,units='occupancy ratio 0–1; synthetic capacity-normalized target',thresholds=dict(LOW='ratio < 0.4',MEDIUM='0.4 <= ratio < 0.7',HIGH='ratio >= 0.7'),stops=rows)

@router.get('/api/models/insights')
def insights():
    try:
        import os
        if os.getenv('BUSSURE_DISABLE_MODELS')=='1':raise ValueError('Models disabled by BUSSURE_DISABLE_MODELS')
        meta=get_bundle().meta
        models={k:{key:value for key,value in v.items() if key not in ('mean','std','validation_history')} for k,v in meta['models'].items()}
        status='LOADED_AND_VALIDATED'
        reason=None
    except (ImportError,OSError,ValueError,RuntimeError,KeyError) as exc:
        models={};status='BASELINE_FALLBACK';reason=str(exc)
    import json
    original=json.loads((ROOT/'ml/travel_time/dcrnn_v2/sunt_dev_artifacts/model_config.json').read_text())
    return dict(status=status,fallback_reason=reason,data_source='SYNTHETIC',models=models,original_experiments=dict(dcrnn=dict(dataset='Historical Salvador Brazil',config=original,usage='Separate historical-demo API only; incompatible graph'),stgcn=dict(nodes=10,features=8,usage='Archived checkpoint inspected with weights_only=True; original architecture source absent. New 7-stop ST-GCN trained separately. Historical metrics do not apply.')),limitations=['5/15-minute forecast horizons use saved synthetic test-day 34 histories, not live operational observations','Whole-journey forecasts hold short-horizon predictions fixed as explicit planning assumptions','Reliability is a deterministic index, not a calibrated probability'])

class ScenarioInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    event_type:Literal['ROAD_BLOCK','CONGESTION','BREAKDOWN','TEMPORARY_DELAY','HEAVY_RAIN','CROWD_SURGE']
    route_id:str
    severity:Literal['LOW','MODERATE','HIGH','CRITICAL']='HIGH'
    duration_minutes:int=Field(default=30,ge=1,le=180)

@router.post('/api/simulation/scenarios',status_code=201)
async def scenario(body:ScenarioInput,request:Request):
    gtfs=active_network(request)
    if body.route_id not in gtfs.route_trips:raise HTTPException(422,'Unknown synthetic route')
    stop=gtfs.stops[gtfs.trip_stops[gtfs.route_trips[body.route_id][0]][0]['stop_id']]
    now=utc_now()
    event=NetworkEvent(event_id='SYN_SCENARIO_'+uuid4().hex[:12],event_type=body.event_type,route_id=body.route_id,severity=body.severity,latitude=stop['latitude'],longitude=stop['longitude'],start_time=now,end_time=now+timedelta(minutes=body.duration_minutes),description='SYNTHETIC SCENARIO: '+body.event_type.replace('_',' '))
    return getattr(request.app.state,'ai_events',request.app.state.events).create(event)
