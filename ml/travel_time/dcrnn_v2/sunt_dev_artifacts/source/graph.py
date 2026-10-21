"""Directed segment topology derived strictly from consecutive GTFS stop pairs."""
from pathlib import Path
import numpy as np
import pandas as pd


def read_topology(directory):
    directory = Path(directory)
    frames = {}
    required = {'trips.txt': ['trip_id', 'route_id'],
                'routes.txt': ['route_id'], 'stops.txt': ['stop_id'],
                'stop_times.txt': ['trip_id', 'stop_id', 'stop_sequence']}
    for filename, columns in required.items():
        path = directory / filename
        if not path.is_file():
            raise ValueError(f'Missing GTFS file: {path}')
        frame = pd.read_csv(path, dtype=str)
        if not set(columns).issubset(frame.columns) or frame[columns].isna().any().any():
            raise ValueError(f'{path} must contain nonempty columns {columns}')
        frames[filename] = frame
    trips, times = frames['trips.txt'], frames['stop_times.txt'].copy()
    if trips.trip_id.duplicated().any():
        raise ValueError('GTFS trip_id must be unique in trips.txt')
    if not set(trips.route_id).issubset(set(frames['routes.txt'].route_id)):
        raise ValueError('GTFS trips reference unknown routes')
    if not set(times.trip_id).issubset(set(trips.trip_id)) or not set(times.stop_id).issubset(set(frames['stops.txt'].stop_id)):
        raise ValueError('GTFS stop_times reference unknown trips/stops')
    times['stop_sequence'] = pd.to_numeric(times.stop_sequence, errors='raise')
    if times.duplicated(['trip_id', 'stop_sequence']).any():
        raise ValueError('GTFS trip stop_sequence values must be unique')
    routes = dict(zip(trips.trip_id, trips.route_id))
    pairs, edges = {}, set()
    for trip, group in times.groupby('trip_id', sort=True):
        stops = group.sort_values('stop_sequence').stop_id.tolist()
        segments = [(routes[trip], a, b) for a, b in zip(stops, stops[1:])]
        pairs[trip] = set(segments)
        edges.update(zip(segments, segments[1:]))
    return routes, pairs, edges


def build_graph(nodes, edges):
    index = {node: i for i, node in enumerate(nodes)}
    adjacency = np.zeros((len(nodes), len(nodes)), dtype=np.float32)
    for origin, destination in edges:
        if origin in index and destination in index:
            adjacency[index[origin], index[destination]] = 1
    # Self loops also make isolated nodes valid random walks. Persist the raw graph.
    augmented = adjacency + np.eye(len(nodes), dtype=np.float32)
    supports = np.stack([augmented / augmented.sum(1, keepdims=True),
                         augmented.T / augmented.T.sum(1, keepdims=True)])
    return adjacency, supports.astype(np.float32)
