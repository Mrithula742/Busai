from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from .stops import require_gtfs
from ..schemas.journey import JourneyResults
from ..services.journey_service import stop_summary

router = APIRouter()


@router.get('/api/stops/search')
async def search_stops(request: Request, q: str = Query(..., min_length=1, max_length=100), limit: int = Query(10, ge=1, le=30)):
    gtfs = require_gtfs(request)
    query = q.strip().casefold()
    results = [] if not query else [stop_summary(s) for s in gtfs.stops.values() if query in s['stop_name'].casefold() or query == s['stop_id'].casefold()]
    results.sort(key=lambda s: (not s['stop_name'].casefold().startswith(query), s['stop_name']))
    return {'data_source': gtfs.data_source, 'stops': results[:limit]}


@router.get('/api/transit/catalog')
async def catalog(request: Request):
    gtfs = require_gtfs(request)
    return {'data_source': gtfs.data_source,
            'routes': [{'route_id': r['route_id'], 'route_short_name': r.get('route_short_name', ''), 'route_long_name': r.get('route_long_name', '')} for r in gtfs.routes.values()],
            'stops': [stop_summary(gtfs.stops[sid]) for sid in sorted(gtfs.stops)]}


@router.get('/api/journeys/options', response_model=JourneyResults)
async def journey_options(request: Request, latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180), destination: str = Query(..., min_length=1, max_length=200), radius: float = Query(1000, gt=0, le=5000), preference: Optional[Literal['faster', 'less_crowd', 'fewer_transfers']] = None):
    require_gtfs(request)
    request.app.state.gps.refresh_stale()
    try:
        return request.app.state.journeys.search(latitude, longitude, destination, radius, preference)
    except KeyError as exc:
        raise HTTPException(404, 'Destination stop is not in the loaded GTFS; choose a search suggestion') from exc
