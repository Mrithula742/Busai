import asyncio
import json
import sys
import time
import unittest
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'simulator'))
from app.config import Settings
from app.main import create_app
from app.schemas.network_event import NetworkEvent
from app.services.gtfs_service import GTFSService
from app.utils.time_utils import utc_now
from app.utils.geo import haversine_meters, walking_minutes
from app.websocket.manager import ConnectionManager
from multi_bus_simulator import SimulatedBus

SAMPLE = ROOT / 'simulator/routes/sample_gtfs'


def payload(bus_id='TEST_BUS', source='simulated', age=0):
    return dict(bus_id=bus_id, route_id='SAMPLE_R1', trip_id='SAMPLE_T1', latitude=13, longitude=80, speed=5, timestamp=(utc_now() - timedelta(seconds=age)).isoformat(), source=source)


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(Settings(gtfs_dir=SAMPLE, sample_data=True, stale_seconds=0.3)))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def test_sources_filters_and_validation(self):
        for name, source in [('SIM', 'simulated'), ('PHONE', 'real_phone')]:
            response = self.client.post('/api/buses/location', json=payload(name, source))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['route_verified'])
        self.assertEqual(len(self.client.get('/api/buses').json()), 2)
        self.assertEqual(len(self.client.get('/api/routes/SAMPLE_R1/buses').json()), 2)
        self.assertEqual(self.client.get('/api/buses/absent').status_code, 404)
        self.assertEqual(self.client.post('/api/buses/location', json=payload('SIM', 'real_phone')).status_code, 409)
        bad = payload(); bad['latitude'] = 91
        self.assertEqual(self.client.post('/api/buses/location', json=bad).status_code, 422)
        bad = payload(); bad['timestamp'] = '2026-01-01T00:00:00'
        self.assertEqual(self.client.post('/api/buses/location', json=bad).status_code, 422)
        self.assertEqual(self.client.post('/api/buses/location', json=payload(age=-60)).status_code, 409)
        unknown = payload('UNKNOWN'); unknown['trip_id'] = 'prototype'
        self.assertFalse(self.client.post('/api/buses/location', json=unknown).json()['route_verified'])

    def test_websocket_fanout_and_stale(self):
        with self.client.websocket_connect('/ws/buses') as a, self.client.websocket_connect('/ws/buses') as b:
            self.assertEqual(a.receive_json()['type'], 'ready')
            b.receive_json()
            update = payload()
            self.client.post('/api/buses/location', json=update)
            self.assertEqual(a.receive_json()['bus']['status'], 'MOVING')
            self.assertEqual(b.receive_json()['bus']['bus_id'], 'TEST_BUS')
            self.assertEqual(self.client.post('/api/buses/location', json=update).status_code, 200)
            self.assertEqual(a.receive_json()['bus']['status'], 'STALE')
            self.assertEqual(b.receive_json()['bus']['status'], 'STALE')
        self.assertEqual(self.client.get('/api/buses').json(), [])
        self.assertEqual(self.client.get('/api/buses/TEST_BUS').json()['status'], 'STALE')
        self.assertEqual(len(self.client.get('/api/buses?include_stale=true').json()), 1)
        self.assertEqual(self.client.post('/api/buses/location', json=payload()).json()['status'], 'MOVING')

    def test_old_fix_cannot_appear_live(self):
        response = self.client.post('/api/buses/location', json=payload(age=60))
        self.assertEqual(response.json()['status'], 'STALE')

    def test_gtfs_nearby_and_directed_connections(self):
        nearby = self.client.get('/api/stops/nearby?lat=13&lon=80&radius=2000').json()
        distances = [s['distance_meters'] for s in nearby]
        self.assertEqual(distances, sorted(distances))
        self.assertEqual(nearby[0]['stop_id'], 'SAMPLE_W')
        self.assertEqual(nearby[0]['data_source'], 'SAMPLE')
        self.assertEqual(len(self.client.get('/api/stops/SAMPLE_C/routes').json()['routes']), 3)
        forward = self.client.get('/api/routes/connections?origin=SAMPLE West&destination=SAMPLE East').json()['connections']
        self.assertEqual(forward[0]['route_short_name'], 'SAMPLE-A')
        reverse = self.client.get('/api/routes/connections?origin=SAMPLE East&destination=SAMPLE West').json()['connections']
        self.assertEqual(reverse, [])
        self.assertEqual(len(self.client.get('/api/trips/SAMPLE_T1/stops').json()['stops']), 3)
        self.assertEqual(self.client.get('/api/stops/nearby?lat=100&lon=80').status_code, 422)
        self.assertAlmostEqual(walking_minutes(840), 10)
        self.assertAlmostEqual(haversine_meters(0, 0, 0, 1), 111195, delta=1)

    def test_missing_gtfs_and_phone_page(self):
        with TestClient(create_app(Settings(gtfs_dir=ROOT / 'datasets/gtfs'))) as client:
            self.assertEqual(client.get('/api/stops/nearby?lat=13&lon=80').status_code, 503)
            self.assertEqual(client.get('/health').json()['data_source'], 'unavailable')
            self.assertEqual(client.get('/gps-device').status_code, 200)
            self.assertFalse(client.post('/api/buses/location', json=payload()).json()['route_verified'])

    def test_simulator_stop_sequence_and_dwell(self):
        gtfs = GTFSService(SAMPLE, sample=True)
        bus = SimulatedBus(dict(bus_id='TEST', route_id='SAMPLE_R1', trip_id='SAMPLE_T1', speed_mps=10, start_progress=0), gtfs, 6)
        first = bus.payload()
        bus.advance(2)
        self.assertGreater(bus.payload()['longitude'], first['longitude'])
        bus.advance(bus.lengths[0] / 10 - 2 + 1)
        self.assertEqual(bus.payload()['current_stop_id'], 'SAMPLE_C')
        self.assertEqual(bus.payload()['status'], 'STOPPED')
        bus.advance(6)
        self.assertEqual(bus.payload()['next_stop_id'], 'SAMPLE_E')
        self.assertEqual(bus.payload()['source'], 'SIMULATOR')

    def test_slow_viewer_queue_and_event_contract(self):
        manager = ConnectionManager()
        queue = asyncio.Queue(maxsize=128)
        manager.clients['test'] = queue
        bus = self.client.post('/api/buses/location', json=payload()).json()
        from app.schemas.bus import BusState
        for _ in range(129):
            manager.publish(BusState(**bus))
        self.assertEqual(queue.get_nowait()['type'], 'resync_required')
        event = dict(event_id='E1', event_type='ROAD_BLOCK', latitude=13, longitude=80, start_time=utc_now(), description='Future interface test')
        self.assertEqual(NetworkEvent(**event).event_type, 'ROAD_BLOCK')
        with self.assertRaises(ValueError):
            NetworkEvent(**event, end_time=utc_now() - timedelta(days=1))


if __name__ == '__main__':
    unittest.main()
