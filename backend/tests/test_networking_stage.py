import asyncio
import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'simulator'))
from app.config import Settings
from app.main import create_app
from app.services.gtfs_service import GTFSService, load_gtfs
from app.utils.time_utils import utc_now
from app.schemas.gps import GPSUpdate
from multi_bus_simulator import SimulatedBus
from network_event_hook import active_events_for_bus, apply_network_events

SAMPLE = ROOT / 'simulator/routes/sample_gtfs'


def fix(bus_id='PHONE_TEST', source='REAL_PHONE_GPS', **changes):
    data = dict(bus_id=bus_id, source=source, route_id='SAMPLE_R1', trip_id='SAMPLE_T1', latitude=13.0, longitude=80.0, accuracy=5, speed=None, heading=None, timestamp=utc_now().isoformat())
    data.update(changes)
    return data


def event(event_id='TEST_EVENT', **changes):
    data = dict(event_id=event_id, event_type='ROAD_BLOCK', latitude=13, longitude=80, route_id='SAMPLE_R1', trip_id='SAMPLE_T1', severity='HIGH', start_time=utc_now().isoformat(), description='Automated SAMPLE event')
    data.update(changes)
    return data


class CompleteNetworkingTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(Settings(gtfs_dir=SAMPLE, stale_seconds=30)))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def test_canonical_sources_and_fields_coexist(self):
        for name, source in [('PHONE_TEST', 'REAL_PHONE_GPS'), ('SIM_TEST', 'SIMULATOR')]:
            response = self.client.post('/api/buses/location', json=fix(name, source))
            self.assertEqual(response.status_code, 200, response.text)
            bus = response.json()
            self.assertEqual(bus['source'], source)
            self.assertEqual(bus['accuracy'], 5)
            self.assertEqual(bus['last_received_at'], bus['received_at'])
            self.assertEqual(bus['current_stop_id'], 'SAMPLE_W')
            self.assertEqual(bus['next_stop_id'], 'SAMPLE_C')
        self.assertEqual(len(self.client.get('/api/buses').json()), 2)
        self.assertEqual(self.client.post('/api/buses/location', json=fix('PHONE_TEST', 'SIMULATOR')).status_code, 409)
        for source in ('real_phone', 'simulated'):
            response = self.client.post('/api/buses/location', json=fix(source, source))
            self.assertIn(response.json()['source'], ('REAL_PHONE_GPS', 'SIMULATOR'))

    def test_retry_is_idempotent_without_freshening_fix(self):
        update = fix(timestamp=(utc_now() - timedelta(seconds=60)).isoformat())
        first = self.client.post('/api/buses/location', json=update).json()
        again = self.client.post('/api/buses/location', json=update).json()
        self.assertEqual(first, again)
        self.assertEqual(again['status'], 'STALE')
        update['longitude'] += .01
        self.assertEqual(self.client.post('/api/buses/location', json=update).status_code, 409)

    def test_invalid_values_and_unknown_source(self):
        for change in ({'latitude': -91}, {'longitude': 181}, {'accuracy': -1}, {'heading': 360}, {'source': 'official_live'}, {'bus_id': ' '}, {'timestamp': '2026-10-03T08:00:00'}):
            self.assertEqual(self.client.post('/api/buses/location', json=fix(**change)).status_code, 422, change)
        for field in ('latitude', 'longitude', 'accuracy'):
            with self.assertRaises(ValueError):
                GPSUpdate(**fix(**{field: float('nan')}))

    def test_phone_stop_progression_and_weak_accuracy(self):
        self.client.post('/api/buses/location', json=fix())
        weak = self.client.post('/api/buses/location', json=fix(longitude=80.005, accuracy=200)).json()
        self.assertEqual(weak['current_stop_id'], 'SAMPLE_W')
        moved = self.client.post('/api/buses/location', json=fix(longitude=80.005)).json()
        self.assertEqual((moved['current_stop_id'], moved['next_stop_id']), ('SAMPLE_C', 'SAMPLE_E'))
        final = self.client.post('/api/buses/location', json=fix(longitude=80.01)).json()
        self.assertEqual(final['current_stop_id'], 'SAMPLE_E')
        self.assertIsNone(final['next_stop_id'])
        unknown = self.client.post('/api/buses/location', json=fix(trip_id='prototype')).json()
        self.assertFalse(unknown['route_verified'])
        self.assertIsNone(unknown['current_stop_id'])

    def test_passenger_nearby_has_no_bus_side_effect(self):
        response = self.client.get('/api/stops/nearby?latitude=13&longitude=80&radius=2000&limit=2')
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['distance_meters'], 0)
        self.assertEqual(rows[0]['estimated_walking_minutes'], 0)
        self.assertLessEqual(rows[0]['distance_meters'], rows[1]['distance_meters'])
        self.assertEqual(self.client.get('/api/buses').json(), [])
        for query in ('limit=0', 'latitude=91', 'radius=-1', 'lat=14'):
            self.assertEqual(self.client.get('/api/stops/nearby?latitude=13&longitude=80&' + query).status_code, 422)

    def test_gtfs_methods_route_detail_and_direction(self):
        gtfs = self.client.app.state.gtfs
        self.assertEqual(gtfs.data_source, 'SAMPLE')
        self.assertEqual(gtfs.get_stop('SAMPLE_W')['latitude'], 13)
        self.assertEqual(len(gtfs.get_routes_for_stop('SAMPLE_C')), 3)
        self.assertEqual(len(gtfs.get_trip_stop_sequence('SAMPLE_T1')), 3)
        self.assertEqual(len(gtfs.get_stops_for_route('SAMPLE_R1')), 3)
        self.assertEqual(len(gtfs.get_routes_between_stops('SAMPLE_W', 'SAMPLE_E')), 2)
        self.assertEqual(gtfs.get_routes_between_stops('SAMPLE_E', 'SAMPLE_W'), [])
        self.assertEqual(len(gtfs.get_routes_near_location(13, 80, 5)), 2)
        self.assertEqual(self.client.get('/api/routes/SAMPLE_R1').json()['route']['route_short_name'], 'SAMPLE-A')
        self.assertEqual(self.client.get('/api/routes/absent').status_code, 404)
        self.assertEqual(self.client.get('/api/routes/nearby?latitude=13&longitude=80').status_code, 200)
        self.assertEqual(self.client.get('/api/health').json()['status'], 'ok')

    def test_gtfs_sample_selection_and_bad_feed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Fixtures are generated by the test, never downloaded.
            real = root / 'datasets/gtfs'
            real.mkdir(parents=True)
            for name in ('stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt'):
                (real / name).write_text((SAMPLE / name).read_text())
            with patch('app.config.ROOT', root):
                loaded = load_gtfs(Settings(gtfs_dir=SAMPLE, sample_data=True))
                self.assertEqual(loaded.directory, real)
                self.assertEqual(loaded.data_source, 'GTFS')
            with (real / 'routes.txt').open('a') as handle:
                handle.write('SAMPLE_R1,SAMPLE_AGENCY,duplicate,duplicate,3\n')
            with self.assertRaisesRegex(ValueError, 'duplicate route_id'):
                GTFSService(real)

    def test_many_simulated_trips_and_next_bus_order(self):
        config = json.loads((ROOT / 'simulator/simulator_config.json').read_text())
        self.assertEqual(len({b['trip_id'] for b in config['buses']}), 6)
        for item in config['buses']:
            bus = SimulatedBus(item, self.client.app.state.gtfs, 6)
            response = self.client.post('/api/buses/location', json=bus.payload())
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.client.get('/api/buses').json()), 6)
        response = self.client.get('/api/routes/SAMPLE_R1/stops/SAMPLE_E/approaching')
        ordered = response.json()['buses']
        self.assertEqual([b['bus']['bus_id'] for b in ordered], ['BUS_002', 'BUS_001'])
        self.assertNotIn('eta', response.text.lower())

    def test_event_create_broadcast_clear_resync(self):
        with self.client.websocket_connect('/ws/buses') as socket:
            ready = socket.receive_json()
            self.assertEqual(ready['snapshot_url'], '/api/snapshot')
            response = self.client.post('/api/network-events', json=event())
            self.assertEqual(response.status_code, 201, response.text)
            created = socket.receive_json()
            self.assertEqual(created['type'], 'NETWORK_EVENT_CREATED')
            snapshot = self.client.get('/api/snapshot').json()
            self.assertEqual(snapshot['epoch'], ready['epoch'])
            self.assertEqual(snapshot['revision'], created['revision'])
            self.assertEqual(len(snapshot['network_events']), 1)
            self.assertEqual(self.client.post('/api/network-events', json=event()).status_code, 409)
            self.assertEqual(self.client.post('/api/network-events/TEST_EVENT/clear').status_code, 200)
            cleared = socket.receive_json()
            self.assertEqual(cleared['type'], 'NETWORK_EVENT_CLEARED')
            self.assertEqual(cleared['event']['status'], 'CLEARED')
            self.assertGreater(cleared['revision'], created['revision'])
            revision = self.client.get('/api/snapshot').json()['revision']
            self.client.post('/api/network-events/TEST_EVENT/clear')
            self.assertEqual(self.client.get('/api/snapshot').json()['revision'], revision)
        with self.client.websocket_connect('/ws/buses') as reconnected:
            self.assertEqual(reconnected.receive_json()['epoch'], ready['epoch'])
            self.assertEqual(self.client.get('/api/snapshot').json()['network_events'][0]['status'], 'CLEARED')
        self.assertEqual(self.client.get('/api/network-events').json(), [])
        self.assertEqual(self.client.post('/api/network-events/missing/clear').status_code, 404)

    def test_events_expire_and_invalid_contract(self):
        # Future start is supported; hook must not activate it yet.
        response = self.client.post('/api/network-events', json=event(end_time=(utc_now() + timedelta(seconds=10)).isoformat()))
        self.assertEqual(response.status_code, 201)
        service = self.client.app.state.events
        future = utc_now() + timedelta(seconds=20)
        with patch('app.services.network_event_service.utc_now', return_value=future):
            service.expire()
        self.assertEqual(service.events['TEST_EVENT'].status, 'CLEARED')
        invalid = event('BAD', end_time=(utc_now() - timedelta(days=1)).isoformat())
        self.assertEqual(self.client.post('/api/network-events', json=invalid).status_code, 422)
        self.assertEqual(self.client.post('/api/network-events', json=event('OTHER', event_type='OTHER')).status_code, 201)

    def test_event_hook_matches_time_route_trip_and_stops_for_roadblock(self):
        bus = SimulatedBus(dict(bus_id='HOOK', route_id='SAMPLE_R1', trip_id='SAMPLE_T1', speed_mps=7, start_progress=0), self.client.app.state.gtfs, 6)
        events = [dict(event(), status='ACTIVE'), dict(event('FUTURE', start_time=(utc_now() + timedelta(hours=1)).isoformat()), status='ACTIVE'), dict(event('OTHER_ROUTE', route_id='SAMPLE_R2'), status='ACTIVE')]
        applicable = active_events_for_bus(events, bus, utc_now())
        self.assertEqual(len(applicable), 1)
        apply_network_events(bus, applicable, 2)
        self.assertEqual(bus.speed, 7)
        self.assertAlmostEqual(bus.offset, 0)
        self.assertEqual(bus.display_speed, 0)
        self.assertAlmostEqual(bus.delay_seconds, 2)
        self.assertEqual(len(bus.network_events), 1)

    def test_status_event_and_monotonic_snapshot_revisions(self):
        with self.client.websocket_connect('/ws/buses') as socket:
            socket.receive_json()
            self.client.post('/api/buses/location', json=fix())
            update = socket.receive_json()
            self.assertEqual(update['type'], 'BUS_LOCATION_UPDATED')
            future = utc_now() + timedelta(seconds=31)
            with patch('app.services.bus_state_service.utc_now', return_value=future):
                self.client.get('/api/buses')
            stale = socket.receive_json()
            self.assertEqual(stale['type'], 'BUS_STATUS_CHANGED')
            self.assertEqual(stale['bus']['status'], 'STALE')
            self.assertGreater(stale['revision'], update['revision'])
            self.assertEqual(self.client.get('/api/snapshot').json()['revision'], stale['revision'])


if __name__ == '__main__':
    unittest.main()
