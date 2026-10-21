"""Train an independent V2 bundle from measured segment traversal records.

Run with --inspect first to report the data, graph, splits and tensor shapes.
An existing output directory is never overwritten.
"""
import argparse
import json
import random
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from .artifacts import sha256, write_json, write_manifest
from .dataset import WindowDataset
from .graph import read_topology, build_graph
from .model import DCRNN
from .preprocess import FEATURES, FEATURE_PATH, REQUIRED, aggregate, fit_scaler, prepare_features, read_observations, split_windows

HERE = Path(__file__).parent


def validate_config(config):
    integers = ['sequence_length', 'prediction_horizon', 'bin_minutes', 'min_train_observations_per_node',
                'hidden_dim', 'num_layers', 'diffusion_steps', 'batch_size', 'epochs', 'patience']
    required = integers + ['train_fraction', 'validation_fraction', 'dropout', 'learning_rate', 'gradient_clip', 'weight_decay', 'seed']
    if not set(required).issubset(config):
        raise ValueError(f'Missing training configuration fields: {sorted(set(required)-set(config))}')
    if type(config['seed']) is not int or not 0 <= config['seed'] < 2**32:
        raise ValueError('seed must be an integer between 0 and 2**32-1')
    for key in integers:
        if type(config[key]) is not int or config[key] < 1:
            raise ValueError(f'{key} must be a positive integer')
    if 1440 % config['bin_minutes']:
        raise ValueError('bin_minutes must divide a UTC day exactly')
    train, val = config['train_fraction'], config['validation_fraction']
    if not 0 < train < 1 or not 0 < val < 1 or train + val >= 1:
        raise ValueError('Train and validation fractions must be positive with sum below 1')
    if not 0 <= config['dropout'] < 1:
        raise ValueError('dropout must be in [0, 1)')
    for key in ['learning_rate', 'gradient_clip']:
        if not np.isfinite(config[key]) or config[key] <= 0:
            raise ValueError(f'{key} must be finite and positive')
    if not np.isfinite(config['weight_decay']) or config['weight_decay'] < 0:
        raise ValueError('weight_decay must be finite and nonnegative')


def prepare(observation_path, gtfs, config, data_kind='observed'):
    validate_config(config)
    if not Path(observation_path).is_file():
        raise ValueError(f'Missing measured traversal CSV: {observation_path}. GTFS schedules are not observed travel times.')
    routes, pairs, edges = read_topology(gtfs)
    if data_kind not in ['observed', 'synthetic']:
        raise ValueError('data_kind must be observed or synthetic')
    if data_kind == 'observed' and ((Path(gtfs)/'SAMPLE').exists() or any(t.startswith('SAMPLE_') for t in routes)):
        raise ValueError('Fictional SAMPLE GTFS cannot be used for observed-data training')
    frame = read_observations(observation_path, routes, pairs)
    candidates = sorted(set(frame.node))
    grid, all_values = aggregate(frame, candidates, config['bin_minutes'])
    train_end = int(len(grid) * config['train_fraction'])
    val_end = int(len(grid) * (config['train_fraction'] + config['validation_fraction']))
    eligible = np.isfinite(all_values[:train_end]).sum(0) >= config['min_train_observations_per_node']
    nodes = [node for node, keep in zip(candidates, eligible) if keep]
    if not nodes:
        raise ValueError('No segments have sufficient TRAIN observations; supply real history or review the minimum count')
    values = all_values[:, eligible]
    scaler = fit_scaler(values[:train_end])
    features, targets, observed = prepare_features(grid, values, scaler)
    splits = split_windows(observed, config['sequence_length'], config['prediction_horizon'], train_end, val_end)
    adjacency, supports = build_graph(nodes, edges)
    model_config = {k: config[k] for k in ['hidden_dim', 'num_layers', 'diffusion_steps', 'dropout', 'sequence_length', 'prediction_horizon']}
    model_config.update(num_nodes=len(nodes), input_dim=len(FEATURES))
    report = {'data_kind': data_kind, 'dataset': str(Path(observation_path).resolve()), 'rows': len(frame),
              'candidate_nodes': len(candidates), 'selected_nodes': len(nodes),
              'excluded_nodes_without_training_coverage': len(candidates)-len(nodes),
              'nodes': [list(n) for n in nodes], 'directed_graph_edges': int(adjacency.sum()),
              'target': 'next-bin mean measured segment traversal seconds', 'features': FEATURES,
              'sequence_length': config['sequence_length'], 'prediction_horizon': config['prediction_horizon'],
              'bin_minutes': config['bin_minutes'], 'utc_bin_count': len(grid),
              'validation_start': grid[train_end].isoformat(), 'test_start': grid[val_end].isoformat(),
              'split_fractions': [config['train_fraction'], config['validation_fraction'], 1-config['train_fraction']-config['validation_fraction']],
              'window_counts': {key: len(value) for key, value in splits.items()},
              'input_shape': ['batch', config['sequence_length'], len(nodes), len(FEATURES)],
              'output_shape': ['batch', config['prediction_horizon'], len(nodes)],
              'observed_target_fraction': float(observed.mean())}
    return dict(frame=frame, grid=grid, nodes=nodes, features=features, targets=targets, observed=observed,
                splits=splits, scaler=scaler, adjacency=adjacency, supports=supports,
                routes=routes, pairs=pairs, model_config=model_config, report=report)


def metrics(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=np.float64), np.asarray(predicted, dtype=np.float64)
    if not len(actual) or not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError('Metrics require finite observed targets and predictions')
    errors = predicted - actual
    variance = np.square(actual - actual.mean()).sum()
    denominator = np.abs(actual).sum()
    return {'MAE_seconds': float(np.abs(errors).mean()), 'RMSE_seconds': float(np.sqrt(np.square(errors).mean())),
            'R2': float(1-np.square(errors).sum()/variance) if variance > 0 else None,
            'WAPE_percent': float(100*np.abs(errors).sum()/denominator) if denominator > 0 else None,
            'observed_target_count': int(len(actual))}


def evaluate(model, loader, mean, std):
    actual, predicted, baseline = [], [], []
    model.eval()
    with torch.no_grad():
        for x, y, mask in loader:
            output = (model(x) * std + mean).clamp_min(0)
            truth = y * std + mean
            persistence = (x[:, -1, :, 0] * std + mean).unsqueeze(1).expand_as(truth).clamp_min(0)
            actual.extend(truth[mask].tolist())
            predicted.extend(output[mask].tolist())
            baseline.extend(persistence[mask].tolist())
    return {'model': metrics(actual, predicted), 'persistence': metrics(actual, baseline)}


def train(observation_path, gtfs, output, config, data_kind='observed'):
    data = prepare(observation_path, gtfs, config, data_kind)
    print(json.dumps(data['report'], indent=2))  # report before optimization starts
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    seed = config['seed']
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    model = DCRNN(**data['model_config'], supports=data['supports'])
    optimizer = torch.optim.Adam(model.parameters(), lr=config['learning_rate'], weight_decay=config['weight_decay'])
    loaders = {}
    for name, starts in data['splits'].items():
        dataset = WindowDataset(data['features'], data['targets'], data['observed'], starts,
                                config['sequence_length'], config['prediction_horizon'])
        loaders[name] = DataLoader(dataset, batch_size=config['batch_size'], shuffle=name == 'train',
                                   generator=torch.Generator().manual_seed(seed), num_workers=0)
    mean, std = (torch.tensor(data['scaler'][key], dtype=torch.float32) for key in ['mean', 'std'])
    history, best, wait = [], float('inf'), 0
    for epoch in range(1, config['epochs']+1):
        model.train()
        loss_sum, count = 0.0, 0
        for x, y, mask in loaders['train']:
            optimizer.zero_grad(set_to_none=True)
            loss = (model(x)-y).abs()[mask].mean()
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite training loss; inspect input data/scaler')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config['gradient_clip'])
            optimizer.step()
            loss_sum += loss.item()*int(mask.sum()); count += int(mask.sum())
        validation = evaluate(model, loaders['validation'], mean, std)
        mae = validation['model']['MAE_seconds']
        history.append({'epoch': epoch, 'training_MAE_scaled': loss_sum/count, 'validation': validation})
        print(f'Epoch {epoch}: validation MAE={mae:.4f} seconds')
        if mae < best:
            best, wait = mae, 0
            torch.save({'schema_version': 2, 'model_state_dict': model.state_dict(),
                        'model_config': data['model_config'], 'feature_order': FEATURES, 'best_epoch': epoch,
                        'validation': validation, 'seed': seed, 'data_kind': data_kind}, output/'dcrnn_v2_best.pt')
        else:
            wait += 1
            if wait >= config['patience']:
                break
    checkpoint = torch.load(output/'dcrnn_v2_best.pt', map_location='cpu', weights_only=True)
    model.load_state_dict(checkpoint['model_state_dict'], strict=True)
    results = {'best_epoch': checkpoint['best_epoch'], 'epochs_run': len(history),
               'validation': checkpoint['validation'], 'test': evaluate(model, loaders['test'], mean, std),
               'data_kind': data_kind, 'quality_note': 'Compare held-out model error with persistence; training success alone does not establish ETA quality.'}
    for name, value in [('model_config', data['model_config']), ('training_config', config), ('scaler', data['scaler']),
                        ('metrics', results), ('training_history', history), ('data_report', data['report'])]:
        write_json(output/f'{name}.json', value)
    shutil.copyfile(FEATURE_PATH, output/'feature_config.json')
    write_json(output/'node_mapping.json', [dict(node_index=i, route_id=n[0], from_stop_id=n[1], to_stop_id=n[2]) for i, n in enumerate(data['nodes'])])
    write_json(output/'trip_topology.json', {'routes': data['routes'], 'pairs': {k: sorted(v) for k, v in data['pairs'].items()}})
    np.save(output/'adjacency.npy', data['adjacency'], allow_pickle=False)
    np.save(output/'supports.npy', data['supports'], allow_pickle=False)
    np.savez_compressed(output/'prepared_arrays.npz', features=data['features'], targets=data['targets'], observed=data['observed'],
                        timestamps_ns=data['grid'].asi8, **{f'{k}_targets': v for k, v in data['splits'].items()})
    data['frame'][REQUIRED].to_csv(output/'observations.csv', index=False)
    # Save a real held-out inference input and its exact reference output.
    t = int(data['splits']['test'][0])
    as_of = data['grid'][t]
    data['frame'].loc[data['frame'].arrived_at < as_of, REQUIRED].to_csv(output/'sample_observations.csv', index=False)
    model.eval()
    with torch.no_grad():
        raw = model(torch.from_numpy(data['features'][t-config['sequence_length']:t][None]))
        seconds = (raw*std+mean).clamp_min(0)
    write_json(output/'sample_expected.json', {'as_of': as_of.isoformat(), 'input_shape': [1, *data['features'][t-config['sequence_length']:t].shape],
                                             'raw_scaled': raw.tolist(), 'seconds': seconds.tolist()})
    (output/'source').mkdir()
    for path in HERE.iterdir():
        if path.is_file() and path.suffix in ['.py', '.json', '.txt']:
            shutil.copyfile(path, output/'source'/path.name)
    (output/'gtfs').mkdir()
    for filename in ['trips.txt', 'routes.txt', 'stops.txt', 'stop_times.txt']:
        shutil.copyfile(Path(gtfs)/filename, output/'gtfs'/filename)
    write_manifest(output, {'data_kind': data_kind, 'observations_sha256': sha256(observation_path),
                            'python': __import__('platform').python_version(),
                            'packages': {'torch': str(torch.__version__), 'numpy': np.__version__, 'pandas': pd.__version__}})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observations', required=True)
    parser.add_argument('--gtfs', required=True)
    parser.add_argument('--output', default=str(HERE/'artifacts'))
    parser.add_argument('--config', default=str(HERE/'config.json'))
    parser.add_argument('--data-kind', choices=['observed', 'synthetic'], default='observed')
    parser.add_argument('--inspect', action='store_true')
    args = parser.parse_args()
    try:
        config = json.loads(Path(args.config).read_text())
        if args.inspect:
            print(json.dumps(prepare(args.observations, args.gtfs, config, args.data_kind)['report'], indent=2))
        else:
            print(json.dumps(train(args.observations, args.gtfs, args.output, config, args.data_kind), indent=2))
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        parser.exit(2, f'DCRNN V2: {exc}\n')


if __name__ == '__main__':
    main()
