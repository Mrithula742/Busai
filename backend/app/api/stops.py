from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from ..schemas.stop import NearbyStop

router = APIRouter()


def require_gtfs(request):
    gtfs = request.app.state.gtfs
    if not gtfs.loaded:
        raise HTTPException(503, gtfs.error)
    return gtfs


@router.get('/api/stops/nearby', response_model=List[NearbyStop])
async def nearby(request: Request, lat: Optional[float] = Query(None, ge=-90, le=90), lon: Optional[float] = Query(None, ge=-180, le=180), latitude: Optional[float] = Query(None, ge=-90, le=90), longitude: Optional[float] = Query(None, ge=-180, le=180), radius: float = Query(1000, gt=0, le=50000), limit: int = Query(20, ge=1, le=200)):
    if (lat is not None and latitude is not None and lat != latitude) or (lon is not None and longitude is not None and lon != longitude):
        raise HTTPException(422, 'Conflicting coordinate aliases')
    lat = latitude if latitude is not None else lat
    lon = longitude if longitude is not None else lon
    if lat is None or lon is None:
        raise HTTPException(422, 'latitude/longitude (or lat/lon) are required')
    require_gtfs(request)
    return request.app.state.nearby.find_nearby_stops(lat, lon, radius, limit)


@router.get('/api/stops/{stop_id}/routes')
async def stop_routes(stop_id: str, request: Request):
    gtfs = require_gtfs(request)
    if stop_id not in gtfs.stops:
        raise HTTPException(404, 'Unknown stop_id')
    return {'data_source': gtfs.data_source, 'routes': gtfs.get_routes_for_stop(stop_id)}
