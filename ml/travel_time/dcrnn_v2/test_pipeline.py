"""Synthetic unit/integration fixtures only; never create a production checkpoint."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd
import torch
from .artifacts import verify_manifest
from .graph import build_graph
from .inference import DCRNNPredictor, predict_eta
from .model import DCRNN
from .preprocess import fit_scaler, prepare_features, split_windows
from .train import train, prepare


def fixture(directory):
    gtfs = directory/'gtfs'
    gtfs.mkdir()
    pd.DataFrame({'route_id': ['TEST_ROUTE']}).to_csv(gtfs/'routes.txt', index=False)
    pd.DataFrame({'trip_id': ['TEST_TRIP'], 'route_id': ['TEST_ROUTE']}).to_csv(gtfs/'trips.txt', index=False)
    pd.DataFrame({'stop_id': ['A','B','C','D']}).to_csv(gtfs/'stops.txt', index=False)
    pd.DataFrame({'trip_id': ['TEST_TRIP']*4, 'stop_id': ['A','B','C','D'], 'stop_sequence': [1,2,3,4]}).to_csv(gtfs/'stop_times.txt', index=False)
    rows = []
    for t in range(96):
        arrival = pd.Timestamp('2025-01-01T00:00:00Z') + pd.Timedelta(minutes=5*t+4)
        for i,(a,b) in enumerate(zip('ABC','BCD')):
            duration = 50+20*i+8*np.sin(t/6)
            rows.append(dict(trip_id='TEST_TRIP', from_stop_id=a, to_stop_id=b,
                             departed_at=(arrival-pd.Timedelta(seconds=duration)).isoformat(), arrived_at=arrival.isoformat()))
    observations = directory/'synthetic_observations.csv'
    pd.DataFrame(rows).to_csv(observations, index=False)
    config = json.loads(Path(__file__).with_name('config.json').read_text())
    config.update(hidden_dim=4, epochs=3, batch_size=16, dropout=0.0)
    return observations, gtfs, config


class PipelineTests(unittest.TestCase):
    def test_graph_and_model_shapes(self):
        nodes = [('R','A','B'),('R','B','C'),('R','X','Y')]
        adjacency, supports = build_graph(nodes, {(nodes[0],nodes[1])})
        self.assertEqual(adjacency[0,1], 1)
        self.assertEqual(adjacency[1,0], 0)
        np.testing.assert_allclose(supports.sum(-1), 1)
        np.testing.assert_allclose(supports[:,2,2], 1)
        model = DCRNN(3,6,4,2,2,0,12,2,supports)
        output = model(torch.ones(2,12,3,6))
        self.assertEqual(tuple(output.shape), (2,2,3))
        output.sum().backward()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters()))
        with self.assertRaisesRegex(ValueError, 'Expected input'):
            model(torch.ones(2,12,3,5))

    def test_causal_fill_scaling_and_split_boundaries(self):
        values = np.array([[10.0],[np.nan],[20.0],[np.nan],[10000.0]], dtype=np.float32)
        scaler = fit_scaler(values[:3])
        self.assertEqual(scaler['mean'], [15.0])
        grid = pd.date_range('2025-01-01', periods=5, freq='5min', tz='UTC')
        features, targets, observed = prepare_features(grid, values, scaler)
        self.assertEqual(features[1,0,0], features[0,0,0])
        self.assertEqual(features[3,0,0], features[2,0,0])
        self.assertFalse(observed[1,0])
        self.assertEqual(targets[1,0], 0)
        splits = split_windows(np.ones((40,2),dtype=bool), 4, 2, 24, 32)
        self.assertLess(splits['train'][-1]+1, 24)
        self.assertGreaterEqual(splits['validation'][0], 24)
        self.assertLess(splits['validation'][-1]+1, 32)
        self.assertGreaterEqual(splits['test'][0], 32)

    def test_train_save_reload_raw_inference_and_integrity(self):
        with tempfile.TemporaryDirectory(prefix='bussure-v2-test-') as temp:
            root = Path(temp)
            observations, gtfs, config = fixture(root)
            output = root/'synthetic_artifacts'
            with contextlib.redirect_stdout(io.StringIO()):
                results = train(observations, gtfs, output, config, data_kind='synthetic')
            self.assertTrue(np.isfinite(results['test']['model']['MAE_seconds']))
            self.assertEqual(verify_manifest(output)['data_kind'], 'synthetic')
            predictor = DCRNNPredictor(output)
            expected = json.loads((output/'sample_expected.json').read_text())
            sample = output/'sample_observations.csv'
            actual = predictor.predict_all(sample, expected['as_of'])
            np.testing.assert_allclose(actual['raw_scaled'], expected['raw_scaled'][0], atol=1e-5)
            np.testing.assert_allclose(actual['inverse_transformed_seconds'], expected['seconds'][0], atol=1e-4)
            eta = predict_eta(sample, as_of=expected['as_of'], route_id='TEST_ROUTE', from_stop_id='A', to_stop_id='B', artifact_dir=output)
            self.assertGreater(eta['predicted_travel_time_seconds'], 0)
            self.assertEqual(eta['eta_minutes'], eta['predicted_travel_time_seconds']/60)
            self.assertEqual(eta['data_kind'], 'synthetic')
            with self.assertRaisesRegex(ValueError, 'future'):
                predictor.predict_all(observations, expected['as_of'])
            with self.assertRaisesRegex(ValueError, 'aligned'):
                predictor.predict_all(sample, '2025-01-01T01:01:00Z')
            (output/'scaler.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'modified artifact'):
                DCRNNPredictor(output)

    def test_missing_data_and_sample_training_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            observations, gtfs, config = fixture(root)
            with self.assertRaisesRegex(ValueError, 'Missing measured'):
                prepare(root/'missing.csv', gtfs, config)
            (gtfs/'SAMPLE').touch()
            with self.assertRaisesRegex(ValueError, 'Fictional SAMPLE'):
                prepare(observations, gtfs, config)


if __name__ == '__main__':
    unittest.main()
