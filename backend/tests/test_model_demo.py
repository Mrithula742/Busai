import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.main import create_app
from app.api import model_demo


class HistoricalDemoTests(unittest.TestCase):
    def test_actual_checkpoint_and_reference(self):
        with TestClient(create_app()) as client:
            response = client.get('/api/models/historical-demo')
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            self.assertEqual(data['mode'], 'HISTORICAL_DEMO')
            self.assertTrue(data['reference_verified'])
            self.assertTrue(data['as_of'].startswith('2024-06-02'))
            self.assertEqual(len(data['segments']), 9)
            self.assertNotIn('predicted_eta', data)
            for segment in data['segments']:
                self.assertGreaterEqual(segment['predicted_travel_time_seconds'], 0)
                self.assertTrue(segment['from_stop_name'])
            self.assertEqual(client.get('/api/buses').json(), [])

    def test_missing_model_is_recoverable(self):
        with patch.object(model_demo, 'run_demo', side_effect=FileNotFoundError):
            with TestClient(create_app()) as client:
                self.assertEqual(client.get('/api/models/historical-demo').status_code, 503)
                self.assertEqual(client.get('/api/health').status_code, 200)

    def test_busy_does_not_queue_more_inference(self):
        with model_demo._lock:
            with TestClient(create_app()) as client:
                self.assertEqual(client.get('/api/models/historical-demo').status_code, 503)
