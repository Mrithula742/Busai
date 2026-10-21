from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from .stops import require_gtfs

router = APIRouter()


@router.get('/api/routes/nearby')
async def nearby_routes(request: Request, latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180), radius: float = Query(1000, gt=0, le=50000)):
    gtfs = require_gtfs(request)
    return {'data_source': gtfs.data_source, 'routes': gtfs.get_routes_near_location(latitude, longitude, radius)}


@router.get('/api/routes/connections')
async def connections(request: Request, origin: str = Query(..., min_length=1), destination: str = Query(..., min_length=1)):
    gtfs = require_gtfs(request)
    return {'data_source': gtfs.data_source, 'scope': 'static direct connectivity; service calendar not evaluated', 'connections': gtfs.connecting_routes(origin, destination)}


@router.get('/api/routes/{route_id}/buses')
async def route_buses(route_id: str, request: Request, include_stale: bool = False):
    request.app.state.gps.refresh_stale()
    return request.app.state.store.list(include_stale, route_id)


@router.get('/api/routes/{route_id}/stops/{stop_id}/approaching')
async def approaching(route_id: str, stop_id: str, request: Request, limit: int = Query(10, ge=1, le=100)):
    gtfs = require_gtfs(request)
    if route_id not in gtfs.routes or stop_id not in gtfs.route_stops.get(route_id, ()):
        raise HTTPException(404, 'Unknown route or stop not served by route')
    request.app.state.gps.refresh_stale()
    return {'data_source': gtfs.data_source, 'ordering': 'approximate stop-chain distance, not arrival time', 'buses': request.app.state.progression.approaching(request.app.state.store.list(False, route_id), stop_id, limit)}


@router.get('/api/routes/{route_id}/timetable')
async def route_timetable(route_id: str, request: Request, stop_id: Optional[str] = None):
    gtfs = require_gtfs(request)
    if route_id not in gtfs.routes:
        raise HTTPException(404, 'Unknown route_id')
    if stop_id is not None and (stop_id not in gtfs.stops or route_id not in gtfs.stop_routes.get(stop_id, ())):
        raise HTTPException(404, 'Unknown stop_id or stop is not served by route')
    schedules = []
    for trip_id in gtfs.route_trips[route_id]:
        trip = gtfs.trips[trip_id]
        sequence = gtfs.get_trip_stop_sequence(trip_id)
        if not sequence:
            continue
        first_sequence = sequence[0]['stop_sequence']
        for row in sequence:
            if stop_id is not None and row['stop_id'] != stop_id:
                continue
            if stop_id is None and row['stop_sequence'] != first_sequence:
                continue
            schedules.append({'trip_id': trip_id, 'service_id': trip.get('service_id', ''),
                              'stop_id': row['stop_id'], 'stop_sequence': row['stop_sequence'],
                              'arrival_time': row.get('arrival_time', ''),
                              'departure_time': row.get('departure_time', ''),
                              'destination_stop_id': sequence[-1]['stop_id'],
                              'destination_stop_name': gtfs.stops[sequence[-1]['stop_id']]['stop_name']})
    schedules.sort(key=lambda row: (row['departure_time'] or row['arrival_time'], row['trip_id']))
    return {'data_source': gtfs.data_source, 'route_id': route_id, 'stop_id': stop_id,
            'service_calendar_evaluated': False, 'schedules': schedules}


@router.get('/api/routes/{route_id}')
async def route_detail(route_id: str, request: Request):
    gtfs = require_gtfs(request)
    if route_id not in gtfs.routes:
        raise HTTPException(404, 'Unknown route_id')
    return {'data_source': gtfs.data_source, 'route': gtfs.routes[route_id], 'trip_ids': gtfs.route_trips[route_id], 'stops': gtfs.get_stops_for_route(route_id)}


@router.get('/api/trips/{trip_id}/stops')
async def trip_stops(trip_id: str, request: Request):
    gtfs = require_gtfs(request)
    if trip_id not in gtfs.trips:
        raise HTTPException(404, 'Unknown trip_id')
    shape = gtfs.get_trip_shape(trip_id)
    return {'data_source': gtfs.data_source, 'trip_id': trip_id, 'stops': gtfs.trip_stops[trip_id],
            'shape': shape, 'geometry_source': 'GTFS_SHAPE' if shape else 'STOP_SEQUENCE'}
