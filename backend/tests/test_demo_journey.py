import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.main import create_app


class DemoJourneyTests(unittest.TestCase):
    def test_questions_and_no_fake_predictions(self):
        with TestClient(create_app()) as client:
            def ask(question):
                response = client.post('/api/demo/journey', json={'question': question})
                self.assertEqual(response.status_code, 200)
                return response.json()
            result = ask('From Madipakkam to Chennai Central')
            self.assertEqual(len(result['routes']), 2)
            self.assertEqual(result['data_source'], 'FICTIONAL_CHENNAI_DEMO')
            self.assertIsNone(result['predicted_eta'])
            self.assertIsNone(result['predicted_crowd'])
            self.assertEqual(len(ask('From Chennai to Kanchipuram')['routes']), 2)
            self.assertEqual(result['recommended_route_id'], 'DEMO_CHENNAI_A')
            for preference in ['less_crowd', 'less_delay']:
                ranked = client.post('/api/demo/journey', json={'question': 'From Madipakkam to Chennai Central', 'preference': preference}).json()
                self.assertEqual(ranked['recommended_route_id'], 'DEMO_CHENNAI_B')
                for route in ranked['routes']:
                    self.assertEqual(route['metrics_source'], 'SIMULATED_DEMO')
                    self.assertEqual(route['total_minutes'], sum(route[k] for k in ['ride_minutes', 'wait_minutes', 'walking_minutes', 'delay_minutes']))
            self.assertEqual(client.post('/api/demo/journey', json={'question': 'From Chennai to Kanchipuram', 'preference': 'magic'}).status_code, 422)
            self.assertEqual(ask('From nowhere to anywhere')['routes'], [])
            self.assertEqual(ask('From Chennai Central to Madipakkam')['routes'], [])
            self.assertIn('Please ask', ask('hello')['answer'])
            self.assertEqual(client.post('/api/demo/journey', json={'question': ''}).status_code, 422)
