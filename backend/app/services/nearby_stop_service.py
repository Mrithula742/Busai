from ..utils.geo import haversine_meters, walking_minutes


class NearbyStopService:
    def __init__(self, gtfs, walking_speed_mps):
        self.gtfs = gtfs
        self.walking_speed_mps = walking_speed_mps

    def find_nearby_stops(self, latitude, longitude, radius=1000, limit=20):
        results = []
        for stop in self.gtfs.stops.values():
            distance = haversine_meters(latitude, longitude, stop['latitude'], stop['longitude'])
            if distance <= radius:
                results.append({'stop_id': stop['stop_id'], 'stop_name': stop['stop_name'], 'latitude': stop['latitude'], 'longitude': stop['longitude'], 'distance_meters': round(distance, 1), 'walking_minutes': round(walking_minutes(distance, self.walking_speed_mps), 2), 'walking_estimate': 'straight-line approximation', 'data_source': self.gtfs.data_source})
        for result in results:
            result['estimated_walking_minutes'] = result['walking_minutes']
        return sorted(results, key=lambda stop: stop['distance_meters'])[:limit]
