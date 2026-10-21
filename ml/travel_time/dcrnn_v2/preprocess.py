"""Shared offline/online processing of measured, completed segment traversals."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

FEATURE_PATH = Path(__file__).with_name('feature_config.json')
FEATURES = ['travel_time_z', 'observed', 'hour_sin', 'hour_cos', 'weekday_sin', 'weekday_cos']
if json.loads(FEATURE_PATH.read_text())['features'] != FEATURES:
    raise ValueError('feature_config.json order differs from the implemented feature generator')
REQUIRED = ['trip_id', 'from_stop_id', 'to_stop_id', 'departed_at', 'arrived_at']


def utc_timestamp(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError(f'Timestamp must be valid and include a timezone: {value!r}')
    return stamp.tz_convert('UTC')


def read_observations(data, trip_routes, trip_pairs):
    frame = pd.read_csv(data, dtype=str) if isinstance(data, (str, Path)) else pd.DataFrame(data).copy()
    if not set(REQUIRED).issubset(frame.columns) or frame.empty:
        raise ValueError(f'Measured observations are required, with columns {REQUIRED}')
    if frame[REQUIRED].isna().any().any():
        raise ValueError('Observation fields cannot be null')
    for column in REQUIRED[:3]:
        frame[column] = frame[column].astype(str).str.strip()
        if (frame[column] == '').any():
            raise ValueError(f'{column} cannot be blank')
    for column in REQUIRED[3:]:
        frame[column] = pd.to_datetime(frame[column].map(utc_timestamp), utc=True)
    if frame.duplicated(REQUIRED).any():
        raise ValueError('Duplicate traversals must be deduplicated before training/inference')
    frame['travel_time_seconds'] = (frame.arrived_at - frame.departed_at).dt.total_seconds()
    if not np.isfinite(frame.travel_time_seconds).all() or (frame.travel_time_seconds <= 0).any():
        raise ValueError('Every arrival must be after its departure, with finite positive duration')
    nodes = []
    for row in frame.itertuples():
        if row.trip_id not in trip_routes:
            raise ValueError(f'Unknown GTFS trip_id: {row.trip_id}')
        node = (trip_routes[row.trip_id], row.from_stop_id, row.to_stop_id)
        if node not in trip_pairs.get(row.trip_id, set()):
            raise ValueError(f'Observation is not a consecutive GTFS segment: {node} ({row.trip_id})')
        nodes.append(node)
    frame['node'] = nodes
    return frame.sort_values('arrived_at').reset_index(drop=True)


def aggregate(frame, nodes, bin_minutes, end=None):
    frequency = f'{bin_minutes}min'
    frame = frame.copy()
    frame['bin'] = frame.arrived_at.dt.floor(frequency)
    start = frame['bin'].min()
    end = frame['bin'].max() if end is None else end
    grid = pd.date_range(start, end, freq=frequency)
    if len(grid) < 1:
        raise ValueError('No completed observation bins before as_of')
    values = np.full((len(grid), len(nodes)), np.nan, dtype=np.float32)
    node_index, time_index = {n: i for i, n in enumerate(nodes)}, {t: i for i, t in enumerate(grid)}
    for (stamp, node), value in frame.groupby(['bin', 'node']).travel_time_seconds.mean().items():
        if node in node_index and stamp in time_index:
            values[time_index[stamp], node_index[node]] = value
    return grid, values


def fit_scaler(train_values):
    if not np.isfinite(train_values).any(axis=0).all():
        raise ValueError('Every selected node requires observed TRAIN travel times')
    mean = np.nanmean(train_values, axis=0)
    std = np.nanstd(train_values, axis=0)
    std[std < 1e-6] = 1.0
    return {'mean': mean.tolist(), 'std': std.tolist(),
            'fallback': np.nanmedian(train_values, axis=0).tolist(),
            'fitted_on': 'observed training bin means only'}


def prepare_features(grid, values, scaler):
    mean, std, fallback = (np.asarray(scaler[k], dtype=np.float32) for k in ['mean', 'std', 'fallback'])
    if any(a.shape != (values.shape[1],) or not np.isfinite(a).all() for a in [mean, std, fallback]) or (std <= 0).any():
        raise ValueError('Scaler parameters must match node count, be finite, and have positive std')
    observed = np.isfinite(values)
    filled = pd.DataFrame(values).ffill().fillna(pd.Series(fallback)).to_numpy(dtype=np.float32)
    hour = grid.hour.to_numpy() + grid.minute.to_numpy() / 60
    weekday = grid.dayofweek.to_numpy()
    time_features = np.stack([np.sin(2*np.pi*hour/24), np.cos(2*np.pi*hour/24),
                              np.sin(2*np.pi*weekday/7), np.cos(2*np.pi*weekday/7)], -1)
    time_features = np.broadcast_to(time_features[:, None, :], (*values.shape, 4))
    features = np.concatenate([((filled - mean) / std)[..., None], observed[..., None], time_features], -1)
    targets = np.where(observed, (values - mean) / std, 0).astype(np.float32)
    return features.astype(np.float32), targets, observed


def split_windows(observed, sequence_length, horizon, train_end, val_end):
    splits = {}
    for name, left, right in [('train', 0, train_end), ('validation', train_end, val_end), ('test', val_end, len(observed))]:
        starts = [t for t in range(max(left, sequence_length), right - horizon + 1)
                  if observed[t:t+horizon].any() and observed[t-sequence_length:t].any()]
        if not starts:
            raise ValueError(f'No usable {name} windows. Supply more observed time bins for this chronological split.')
        splits[name] = np.asarray(starts, dtype=np.int64)
    return splits
