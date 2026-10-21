from fastapi import APIRouter, HTTPException, Request
from ..schemas.bus import BusState
from typing import List

router = APIRouter()


@router.get('/api/buses', response_model=List[BusState])
async def list_buses(request: Request, include_stale: bool = False):
    request.app.state.gps.refresh_stale()
    return request.app.state.store.list(include_stale)


@router.get('/api/buses/{bus_id}', response_model=BusState)
async def get_bus(bus_id: str, request: Request):
    request.app.state.gps.refresh_stale()
    bus = request.app.state.store.buses.get(bus_id)
    if bus is None:
        raise HTTPException(404, 'Unknown bus_id')
    return bus
