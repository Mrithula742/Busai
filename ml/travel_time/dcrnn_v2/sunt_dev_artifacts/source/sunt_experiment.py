"""Run only the bounded, three-epoch SUNT development experiment on CPU."""
import argparse
import json
from pathlib import Path
import resource
import shutil
import sys
import time
from .artifacts import sha256, write_json, write_manifest
from .train import train


def run(subset, output, config_path):
    subset, output = Path(subset), Path(output)
    config = json.loads(Path(config_path).read_text())
    provenance = json.loads((subset/'sunt_provenance.json').read_text())
    if (config['epochs']>3 or config['batch_size']>16 or config['hidden_dim']>16 or
        config['num_layers']>2 or config['sequence_length']>12 or config['prediction_horizon']!=1 or
        config['diffusion_steps']>2 or provenance['segments']>32 or provenance['rows']>100000):
        raise ValueError('Configuration exceeds the bounded Mac experiment; review a cloud plan before expanding')
    if not provenance.get('final_cutoff_selection_rechecked'):
        raise ValueError('Use the subset with verified connected training-only node selection')
    if config['train_fraction']!=provenance['selection_train_fraction'] or config['min_train_observations_per_node']!=provenance['selection_min_train_observations']:
        raise ValueError('Training settings differ from those used for node selection')
    old = Path(__file__).parent.parent/'dcrnn_v1_final_best.pt'
    old_hash = sha256(old)
    start = time.monotonic()
    results = train(subset/'segment_traversals.csv',subset/'gtfs',output,config,data_kind='observed')
    if sha256(old)!=old_hash:
        raise RuntimeError('Archived V1 checkpoint changed during the run')
    shutil.copyfile(subset/'sunt_provenance.json',output/'sunt_provenance.json')
    report = {'training_seconds':time.monotonic()-start,
              'peak_training_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024),
              'production_ready':False,'target_quality':provenance['target'],
              'trip_id_role':provenance['trip_id_role'],'v1_sha256':old_hash,'v1_unchanged':True,
              'metrics':results,'artifact_bytes_before_manifest':sum(p.stat().st_size for p in output.rglob('*') if p.is_file())}
    write_json(output/'sunt_experiment.json',report)
    original_manifest=json.loads((output/'manifest.json').read_text())
    original_manifest.pop('files')
    original_manifest.update(production_ready=False,target_quality=provenance['target'],trip_id_role=provenance['trip_id_role'])
    write_manifest(output,original_manifest)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subset',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--config',default=str(Path(__file__).with_name('sunt_dev_config.json')))
    args=parser.parse_args()
    try:
        print(json.dumps(run(args.subset,args.output,args.config),indent=2))
    except (ValueError,FileExistsError) as exc:
        parser.exit(2,f'SUNT experiment: {exc}\n')
