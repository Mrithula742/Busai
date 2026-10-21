import csv
from collections import defaultdict
from pathlib import Path
from ..utils.geo import haversine_meters


class GTFSService:
    """Static, directed connectivity only; no claim of service running today."""

    def __init__(self, directory, sample=False):
        self.directory = Path(directory)
        self.data_source = 'SAMPLE' if sample or (self.directory / 'SAMPLE').exists() else 'GTFS'
        self.stops, self.routes, self.trips = {}, {}, {}
        self.shapes = defaultdict(list)
        self.trip_stops = defaultdict(list)
        self.stop_routes = defaultdict(set)
        self.route_trips = defaultdict(list)
        self.route_stops = defaultdict(set)
        self.agencies, self.calendar, self.calendar_dates = [], [], []
        self.loaded = False
        self.error = None
        required = ('stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt')
        if not all((self.directory / name).is_file() for name in required):
            self.error = 'GTFS unavailable: supply stops.txt, routes.txt, trips.txt and stop_times.txt'
            self.data_source = 'unavailable'
            return
        try:
            for row in self.read('stops.txt', ('stop_id', 'stop_name', 'stop_lat', 'stop_lon')):
                if row.get('location_type', '') not in ('', '0'):
                    continue
                lat, lon = float(row['stop_lat']), float(row['stop_lon'])
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError('Invalid stop coordinates')
                if row['stop_id'] in self.stops:
                    raise ValueError('Duplicate stop_id')
                self.stops[row['stop_id']] = dict(row, latitude=lat, longitude=lon)
            for row in self.read('routes.txt', ('route_id',)):
                if not row['route_id'] or row['route_id'] in self.routes:
                    raise ValueError('Empty or duplicate route_id')
                self.routes[row['route_id']] = row
            for row in self.read('trips.txt', ('route_id', 'trip_id', 'service_id')):
                if row['route_id'] not in self.routes:
                    raise ValueError('Trip references unknown route')
                if not row['trip_id'] or row['trip_id'] in self.trips:
                    raise ValueError('Empty or duplicate trip_id')
                self.trips[row['trip_id']] = row
                self.route_trips[row['route_id']].append(row['trip_id'])
            for row in self.read('stop_times.txt', ('trip_id', 'stop_id', 'stop_sequence')):
                if row['trip_id'] not in self.trips or row['stop_id'] not in self.stops:
                    raise ValueError('Stop time references unknown trip or boarding stop')
                row['stop_sequence'] = int(row['stop_sequence'])
                if row['stop_sequence'] < 0:
                    raise ValueError('Negative stop_sequence')
                # Retain only fields used by this stage; do not duplicate full CSV rows.
                self.trip_stops[row['trip_id']].append({key: row.get(key, '') for key in ('stop_id', 'stop_sequence', 'arrival_time', 'departure_time', 'pickup_type', 'drop_off_type')})
                self.stop_routes[row['stop_id']].add(self.trips[row['trip_id']]['route_id'])
                self.route_stops[self.trips[row['trip_id']]['route_id']].add(row['stop_id'])
            for sequence in self.trip_stops.values():
                sequence.sort(key=lambda row: row['stop_sequence'])
                if len({s['stop_sequence'] for s in sequence}) != len(sequence):
                    raise ValueError('Duplicate stop_sequence in trip')
            for row in self.read('shapes.txt', ('shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence')):
                lat, lon, sequence = float(row['shape_pt_lat']), float(row['shape_pt_lon']), int(row['shape_pt_sequence'])
                if not row['shape_id'] or not (-90 <= lat <= 90 and -180 <= lon <= 180) or sequence < 0:
                    raise ValueError('Invalid GTFS shape point')
                self.shapes[row['shape_id']].append((sequence, lat, lon))
            for points in self.shapes.values():
                points.sort(key=lambda point: point[0])
                if len({point[0] for point in points}) != len(points):
                    raise ValueError('Duplicate shape_pt_sequence')
            self.agencies = list(self.read('agency.txt'))
            self.calendar = list(self.read('calendar.txt'))
            self.calendar_dates = list(self.read('calendar_dates.txt'))
            self.loaded = True
        except (ValueError, KeyError, OSError, csv.Error) as exc:
            raise ValueError(f'Invalid GTFS in {self.directory}: {exc}') from exc

    def read(self, name, required=()):
        path = self.directory / name
        if not path.exists():
            return
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            if not set(required).issubset(reader.fieldnames or []):
                raise ValueError(f'{name} missing columns: {required}')
            yield from reader

    def verify(self, route_id, trip_id):
        return self.loaded and self.trips.get(trip_id, {}).get('route_id') == route_id

    def get_stop(self, stop_id):
        return self.stops.get(stop_id)

    def get_routes_for_stop(self, stop_id):
        return [self.routes[r] for r in sorted(self.stop_routes.get(stop_id, ()))]

    def get_trip_stop_sequence(self, trip_id):
        return self.trip_stops.get(trip_id, [])

    def get_trip_shape(self, trip_id):
        shape_id = self.trips.get(trip_id, {}).get('shape_id')
        return [[lat, lon] for _, lat, lon in self.shapes.get(shape_id, ())] if shape_id else []

    def get_stops_for_route(self, route_id):
        return [self.stops[s] for s in sorted(self.route_stops.get(route_id, ()))]

    def get_routes_between_stops(self, origin_stop_id, destination_stop_id):
        return self._connections({origin_stop_id}, {destination_stop_id})

    def get_routes_near_location(self, latitude, longitude, radius=1000):
        distances = {}
        for stop_id, stop in self.stops.items():
            distance = haversine_meters(latitude, longitude, stop['latitude'], stop['longitude'])
            if distance <= radius:
                for route_id in self.stop_routes.get(stop_id, ()):
                    distances[route_id] = min(distance, distances.get(route_id, float('inf')))
        return [dict(self.routes[r], distance_meters=round(d, 1), data_source=self.data_source) for r, d in sorted(distances.items(), key=lambda pair: pair[1])]

    def connecting_routes(self, origin, destination):
        # Areas resolve by literal case-insensitive stop-name substring or exact ID.
        origins = {sid for sid, s in self.stops.items() if sid == origin or origin.casefold() in s['stop_name'].casefold()}
        destinations = {sid for sid, s in self.stops.items() if sid == destination or destination.casefold() in s['stop_name'].casefold()}
        return self._connections(origins, destinations)

    def _connections(self, origins, destinations):
        matches = []
        for trip_id, sequence in self.trip_stops.items():
            for i, boarding in enumerate(sequence):
                if boarding['stop_id'] not in origins or boarding.get('pickup_type') == '1':
                    continue
                for alighting in sequence[i + 1:]:
                    if alighting['stop_id'] in destinations and alighting.get('drop_off_type') != '1':
                        trip = self.trips[trip_id]
                        route = self.routes[trip['route_id']]
                        matches.append({'route_id': trip['route_id'], 'route_short_name': route.get('route_short_name', ''), 'route_long_name': route.get('route_long_name', ''), 'trip_id': trip_id, 'origin_stop_id': boarding['stop_id'], 'destination_stop_id': alighting['stop_id']})
                        break
                else:
                    continue
                break
        return matches


def load_gtfs(settings):
    """Prefer supplied real data over sample fallback. Never mask malformed feeds."""
    from ..config import ROOT
    real = ROOT / 'datasets/gtfs'
    requested = Path(settings.gtfs_dir)
    is_sample_request = settings.sample_data or (requested / 'SAMPLE').exists()
    if is_sample_request and any(real.glob('*.txt')):
        return GTFSService(real)
    service = GTFSService(requested, settings.sample_data)
    if not service.loaded and settings.sample_data:
        return GTFSService(ROOT / 'simulator/routes/sample_gtfs', sample=True)
    return service
