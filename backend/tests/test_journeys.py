import sys
import unittest
from datetime import timedelta
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.config import Settings
from app.main import create_app
from app.utils.time_utils import utc_now


class JourneyTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(Settings(gtfs_dir=ROOT / 'simulator/routes/sample_gtfs')))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def search(self, destination='SAMPLE_E', **params):
        return self.client.get('/api/journeys/options', params=dict(latitude=13, longitude=80.005, destination=destination, **params))

    def bus(self, name, trip='SAMPLE_T1', current='SAMPLE_W', next_stop='SAMPLE_C', lon=80.001, age=0, **changes):
        data = dict(bus_id=name, route_id='SAMPLE_R1', trip_id=trip, latitude=13, longitude=lon, current_stop_id=current, next_stop_id=next_stop, source='SIMULATOR', timestamp=(utc_now() - timedelta(seconds=age)).isoformat())
        data.update(changes)
        response = self.client.post('/api/buses/location', json=data)
        self.assertEqual(response.status_code, 200, response.text)

    def test_case_insensitive_partial_search_and_no_fabrication(self):
        result = self.client.get('/api/stops/search?q=cEnT').json()
        self.assertEqual(result['data_source'], 'SAMPLE')
        self.assertEqual(result['stops'][0]['stop_id'], 'SAMPLE_C')
        self.assertEqual(self.client.get('/api/stops/search?q=Kanchipuram').json()['stops'], [])
        self.assertEqual(self.search('Kanchipuram').status_code, 404)
        self.assertEqual(self.client.get('/api/stops/search?q=%20').json()['stops'], [])

    def test_multiple_direct_routes_and_same_route_vehicles(self):
        north = self.search('SAMPLE_N', radius=100).json()
        self.assertEqual({o['route']['route_id'] for o in north['options']}, {'SAMPLE_R2', 'SAMPLE_R3'})
        self.bus('ONE'); self.bus('TWO', trip='SAMPLE_T1B', lon=80.003)
        east = self.search(radius=100).json()
        self.assertEqual(len(east['options']), 1)
        self.assertEqual({b['bus_id'] for b in east['options'][0]['active_buses']}, {'ONE', 'TWO'})
        self.assertEqual(east['options'][0]['origin_stop']['stop_id'], 'SAMPLE_C')

    def test_passed_at_stop_stale_unknown_and_reverse_buses(self):
        self.bus('PASSED', current='SAMPLE_C', next_stop='SAMPLE_E', lon=80.008)
        self.bus('AT_STOP', current='SAMPLE_C', next_stop='SAMPLE_E', lon=80.005)
        self.bus('STALE', age=90)
        self.bus('UNKNOWN', trip='UNVERIFIED')
        gtfs = self.client.app.state.gtfs
        gtfs.trips['REVERSE'] = dict(route_id='SAMPLE_R1', trip_id='REVERSE', service_id='SAMPLE_DAILY')
        gtfs.route_trips['SAMPLE_R1'].append('REVERSE')
        gtfs.trip_stops['REVERSE'] = [dict(stop_id=s, stop_sequence=i, pickup_type='', drop_off_type='') for i, s in enumerate(['SAMPLE_E', 'SAMPLE_C', 'SAMPLE_W'])]
        self.bus('WRONG_DIRECTION', trip='REVERSE', current='SAMPLE_E', next_stop='SAMPLE_C', lon=80.01)
        result = self.search(radius=100).json()
        self.assertEqual([b['bus_id'] for b in result['options'][0]['active_buses']], ['AT_STOP'])

    def test_no_models_preferences_and_passenger_separation(self):
        result = self.search(radius=100, preference='less_crowd').json()
        self.assertFalse(result['preference_applied'])
        self.assertEqual(result['prediction_status'], 'Prediction model not connected yet')
        for option in result['options']:
            for field in ('predicted_eta', 'predicted_delay', 'predicted_crowd', 'reliability_score'):
                self.assertIsNone(option[field])
        self.assertEqual(self.client.get('/api/buses').json(), [])
        response = self.client.get('/api/journeys/options?latitude=91&longitude=80&destination=SAMPLE_E')
        self.assertEqual(response.status_code, 422)

    def test_no_routes_unknown_progress_and_restricted_boarding(self):
        self.assertEqual(self.search('SAMPLE_W', radius=100).json()['options'], [])
        self.bus('NO_PROGRESS', current=None, next_stop=None, lon=80.002)
        self.assertEqual(self.search(radius=100).json()['options'][0]['active_buses'], [])
        gtfs = self.client.app.state.gtfs
        for trip in ('SAMPLE_T1', 'SAMPLE_T1B'):
            gtfs.trip_stops[trip][1]['pickup_type'] = '1'
        self.assertEqual(self.search(radius=100).json()['options'], [])

    def test_catalog_and_missing_gtfs(self):
        catalog = self.client.get('/api/transit/catalog').json()
        self.assertEqual(len(catalog['routes']), 3)
        self.assertTrue(all(r['route_short_name'].startswith('SAMPLE') for r in catalog['routes']))
        with TestClient(create_app(Settings(gtfs_dir=ROOT / 'datasets/gtfs'))) as client:
            self.assertEqual(client.get('/api/transit/catalog').status_code, 503)
            self.assertEqual(client.get('/api/stops/search?q=test').status_code, 503)


if __name__ == '__main__':
    unittest.main()
