from fastapi import APIRouter, HTTPException, Request
from ..schemas.gps import GPSUpdate
from ..schemas.bus import BusState

router = APIRouter()


@router.post('/api/buses/location', response_model=BusState)
async def update_location(update: GPSUpdate, request: Request):
    try:
        return request.app.state.gps.ingest(update)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
