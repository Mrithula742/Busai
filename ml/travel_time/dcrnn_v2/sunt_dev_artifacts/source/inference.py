"""Cached CPU inference from raw completed traversals and a saved V2 bundle."""
import argparse
from functools import lru_cache
import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from .artifacts import sha256, verify_manifest
from .model import DCRNN
from .preprocess import FEATURE_PATH, FEATURES, aggregate, prepare_features, read_observations, utc_timestamp

DEFAULT_ARTIFACTS = Path(__file__).with_name('artifacts')


class DCRNNPredictor:
    def __init__(self, artifact_dir):
        self.directory = Path(artifact_dir)
        self.manifest = verify_manifest(self.directory)
        for name in ['model.py', 'preprocess.py']:
            if sha256(self.directory/'source'/name) != sha256(Path(__file__).with_name(name)):
                raise ValueError(f'Training source differs from runtime {name}; use the saved source revision')
        def read(name):
            return json.loads((self.directory/name).read_text())
        self.config = read('training_config.json')
        self.model_config = read('model_config.json')
        self.scaler = read('scaler.json')
        self.mapping = read('node_mapping.json')
        self.nodes = [(row['route_id'], row['from_stop_id'], row['to_stop_id']) for row in self.mapping]
        if [row['node_index'] for row in self.mapping] != list(range(len(self.nodes))) or len(set(self.nodes)) != len(self.nodes):
            raise ValueError('Node mapping must be ordered, contiguous and unique')
        topology = read('trip_topology.json')
        self.routes = topology['routes']
        self.pairs = {k: {tuple(n) for n in v} for k, v in topology['pairs'].items()}
        if read('feature_config.json') != json.loads(FEATURE_PATH.read_text()):
            raise ValueError('Saved preprocessing contract differs from this implementation')
        if self.model_config['num_nodes'] != len(self.nodes) or self.model_config['input_dim'] != len(FEATURES):
            raise ValueError('Model dimensions differ from saved feature/node order')
        for key in ['sequence_length', 'prediction_horizon']:
            if self.config[key] != self.model_config[key]:
                raise ValueError(f'Inconsistent training/model {key}')
        supports = np.load(self.directory/'supports.npy', allow_pickle=False)
        self.model = DCRNN(**self.model_config, supports=supports)
        checkpoint = torch.load(self.directory/'dcrnn_v2_best.pt', map_location='cpu', weights_only=True)
        if checkpoint.get('schema_version') != 2 or checkpoint['model_config'] != self.model_config or checkpoint['feature_order'] != FEATURES:
            raise ValueError('Checkpoint architecture or feature contract mismatch')
        try:
            self.model.load_state_dict(checkpoint['model_state_dict'], strict=True)
        except RuntimeError as exc:
            raise ValueError(f'Checkpoint parameters do not match the V2 architecture: {exc}') from exc
        if not np.array_equal(self.model.supports.numpy(), supports):
            raise ValueError('Checkpoint supports differ from saved graph supports')
        self.model.eval()

    def predict_all(self, observations, as_of):
        as_of = utc_timestamp(as_of)
        frequency = f'{self.config["bin_minutes"]}min'
        if as_of != as_of.floor(frequency):
            raise ValueError(f'as_of must be aligned to a {frequency} UTC boundary')
        frame = read_observations(observations, self.routes, self.pairs)
        if (frame.arrived_at > as_of).any():
            raise ValueError('Observations after as_of would leak future information')
        frame = frame.loc[frame.arrived_at < as_of]
        if frame.empty:
            raise ValueError('No observations available in completed bins before as_of')
        grid, values = aggregate(frame, self.nodes, self.config['bin_minutes'], end=as_of-pd.Timedelta(minutes=self.config['bin_minutes']))
        length = self.config['sequence_length']
        if len(grid) < length:
            raise ValueError(f'Need {length} completed time bins; supplied history covers only {len(grid)}')
        if not np.isfinite(values[-length:]).any():
            raise ValueError('No recent measurements for any trained segment in the input window')
        features, _, observed = prepare_features(grid, values, self.scaler)
        x = torch.from_numpy(features[-length:][None])
        with torch.no_grad():
            raw = self.model(x).numpy()[0]
        seconds = raw*np.asarray(self.scaler['std'])+np.asarray(self.scaler['mean'])
        if not np.isfinite(seconds).all():
            raise ValueError('Model produced nonfinite predictions')
        seconds = np.maximum(seconds, 0)
        predictions = []
        for i, node in enumerate(self.mapping):
            predictions.append({**node, 'predicted_travel_time_seconds': float(seconds[0, i]),
                                'eta_minutes': float(seconds[0, i]/60),
                                'horizon_seconds': seconds[:, i].tolist(),
                                'observed_input_bins': int(observed[-length:, i].sum())})
        return {'data_kind': self.manifest['data_kind'], 'as_of': as_of.isoformat(),
                'scope': 'segment traversal duration; excludes waiting and remaining-distance adjustment',
                'input_shape': list(x.shape), 'raw_scaled': raw.tolist(),
                'inverse_transformed_seconds': seconds.tolist(), 'predictions': predictions}


@lru_cache(maxsize=4)
def get_predictor(artifact_dir=str(DEFAULT_ARTIFACTS)):
    return DCRNNPredictor(artifact_dir)


def predict_eta(input_data, *, as_of, route_id, from_stop_id, to_stop_id, artifact_dir=DEFAULT_ARTIFACTS):
    """Return a selected segment's next-bin travel duration from raw observations.

    input_data is a CSV path, DataFrame or list of traversal records. Provide recent
    history plus the latest earlier measurement per node for causal forward fill.
    This function caches the loaded model; it does not reload for each request.
    """
    predictor = get_predictor(str(Path(artifact_dir).resolve()))
    key = (str(route_id), str(from_stop_id), str(to_stop_id))
    if key not in predictor.nodes:
        raise ValueError(f'Segment was not present in this model training graph: {key}')
    result = predictor.predict_all(input_data, as_of)
    return {**result['predictions'][predictor.nodes.index(key)],
            'data_kind': result['data_kind'], 'as_of': result['as_of'], 'scope': result['scope']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', default=str(DEFAULT_ARTIFACTS))
    parser.add_argument('--observations')
    parser.add_argument('--as-of')
    parser.add_argument('--sample', action='store_true', help='Reproduce the saved held-out sample')
    args = parser.parse_args()
    try:
        directory = Path(args.artifacts)
        if args.sample:
            expected = json.loads((directory/'sample_expected.json').read_text())
            observations, as_of = directory/'sample_observations.csv', expected['as_of']
        elif args.observations and args.as_of:
            observations, as_of = args.observations, args.as_of
        else:
            parser.error('Provide --sample or both --observations and --as-of')
        result = get_predictor(str(directory.resolve())).predict_all(observations, as_of)
        if args.sample:
            if not np.allclose(result['raw_scaled'], expected['raw_scaled'][0], rtol=1e-5, atol=1e-5):
                raise ValueError('Raw sample prediction differs from training-time reference')
            if not np.allclose(result['inverse_transformed_seconds'], expected['seconds'][0], rtol=1e-5, atol=1e-4):
                raise ValueError('Inverse-scaled sample prediction differs from saved reference')
            result['saved_sample_reproduced'] = True
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, FileNotFoundError) as exc:
        parser.exit(2, f'DCRNN V2: {exc}\n')


if __name__ == '__main__':
    main()
