"""Versioned artifact bundle with integrity checks; no executable scaler pickle."""
import hashlib
import json
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def write_manifest(directory, metadata):
    directory = Path(directory)
    files = {str(p.relative_to(directory)): sha256(p) for p in sorted(directory.rglob('*'))
             if p.is_file() and p.name != 'manifest.json'}
    write_json(directory / 'manifest.json', {'schema_version': 2, **metadata, 'files': files})


def verify_manifest(directory):
    directory = Path(directory)
    path = directory / 'manifest.json'
    if not path.is_file():
        raise ValueError(f'Missing artifact manifest: {path}. Run V2 training with measured data first.')
    manifest = json.loads(path.read_text())
    if manifest.get('schema_version') != 2:
        raise ValueError('Unsupported artifact schema version')
    required = {'dcrnn_v2_best.pt', 'model_config.json', 'training_config.json', 'feature_config.json',
                'scaler.json', 'node_mapping.json', 'supports.npy', 'adjacency.npy', 'trip_topology.json'}
    if not required.issubset(manifest['files']):
        raise ValueError(f'Manifest missing required files: {sorted(required-set(manifest["files"]))}')
    for name, expected in manifest['files'].items():
        candidate = (directory / name).resolve()
        if directory.resolve() not in candidate.parents or not candidate.is_file() or sha256(candidate) != expected:
            raise ValueError(f'Missing or modified artifact: {name}')
    return manifest
