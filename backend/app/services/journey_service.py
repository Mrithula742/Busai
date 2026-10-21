from ..utils.geo import haversine_meters
from ..utils.time_utils import utc_now


def stop_summary(stop):
    return {key: stop[key] for key in ('stop_id', 'stop_name', 'latitude', 'longitude')}


def useful_bus(bus, route_id, segments, origin, radius, stale_seconds):
    """Use the bus's own trip occurrence/direction, never route ID alone."""
    if not bus.route_verified or bus.route_id != route_id or bus.status == 'STALE':
        return False
    if (utc_now() - bus.timestamp).total_seconds() >= stale_seconds:
        return False
    index = bus.stop_sequence_index
    if index is None:
        return False
    for segment in segments:
        if bus.trip_id != segment['trip_id']:
            continue
        if index < segment['boarding_index']:
            return True
        if index == segment['boarding_index']:
            # current_stop is also the last passed stop: coordinates disambiguate departure.
            if haversine_meters(bus.latitude, bus.longitude, origin['latitude'], origin['longitude']) <= radius:
                return True
    return False


class JourneyService:
    def __init__(self, gtfs, nearby, store, stop_radius):
        self.gtfs, self.nearby, self.store = gtfs, nearby, store
        self.stop_radius = stop_radius

    def search(self, latitude, longitude, destination_id, radius=1000, preference=None):
        destination = self.gtfs.get_stop(destination_id)
        if destination is None:
            raise KeyError('Destination stop is not in the loaded GTFS')
        # Search all stops within radius, not only the first N geographically nearest.
        nearby = self.nearby.find_nearby_stops(latitude, longitude, radius, len(self.gtfs.stops))
        options = []
        for origin in nearby:
            if origin['stop_id'] == destination_id:
                continue
            for route_id in sorted(self.gtfs.stop_routes.get(origin['stop_id'], set()) & self.gtfs.stop_routes.get(destination_id, set())):
                segments = []
                for trip_id in self.gtfs.route_trips[route_id]:
                    sequence = self.gtfs.get_trip_stop_sequence(trip_id)
                    for i, boarding in enumerate(sequence):
                        if boarding['stop_id'] != origin['stop_id'] or boarding.get('pickup_type', '') not in ('', '0'):
                            continue
                        for j in range(i + 1, len(sequence)):
                            alighting = sequence[j]
                            if alighting['stop_id'] == destination_id and alighting.get('drop_off_type', '') in ('', '0'):
                                segments.append({'trip_id': trip_id, 'boarding_index': i, 'destination_index': j})
                                break
                if not segments:
                    continue
                route = self.gtfs.routes[route_id]
                buses = [bus for bus in self.store.list(False, route_id) if useful_bus(bus, route_id, segments, origin, self.stop_radius, self.store.stale_seconds)]
                options.append({'option_id': f"{route_id}:{origin['stop_id']}:{destination_id}", 'origin_stop': origin,
                                'destination_stop': stop_summary(destination), 'route': route,
                                'eligible_trip_segments': segments, 'active_buses': buses})
        return {'data_source': self.gtfs.data_source, 'options': options, 'boarding_radius_meters': self.stop_radius,
                'stale_seconds': self.store.stale_seconds, 'preference': preference,
                'message': '' if options else 'No direct GTFS route found within the walking search radius. Try another destination or a larger radius.'}
