"""Validated synthetic graph models with an explicit, observable fallback."""
import hashlib
import json
import os
from functools import lru_cache
from ..config import ROOT

ARTIFACTS=ROOT/'ml/synthetic/artifacts'

class ForecastBundle:
    def __init__(self,directory=ARTIFACTS):
        import numpy as np
        import torch
        from ml.synthetic.models import STGCN
        from ml.synthetic.data import FEATURES,ETA_FEATURES,DATA
        from ml.travel_time.dcrnn_v2.model import DCRNN
        self.np,self.torch=np,torch
        torch.set_num_threads(2)
        self.directory=directory
        self.meta=json.loads((directory/'manifest.json').read_text())
        if self.meta['schema_version']!=1:raise ValueError('Unsupported model artifact version')
        if self.meta['features']!={'crowd':FEATURES,'eta':ETA_FEATURES}:raise ValueError('Feature order mismatch')
        if self.meta['dataset_sha256']!=hashlib.sha256((DATA/'manifest.json').read_bytes()).hexdigest():raise ValueError('Dataset manifest differs from training')
        for name,digest in self.meta.get('source_sha256',{}).items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Training source differs from runtime: '+name)
        for name,digest in self.meta.get('gtfs_sha256',{}).items():
            if hashlib.sha256((DATA/name).read_bytes()).hexdigest()!=digest:raise ValueError('Training GTFS changed: '+name)
        required={'crowd.pt','eta.pt','adjacency.npy','supports.npy','replay.npz'}
        if not required.issubset(self.meta['files']):raise ValueError('Incomplete artifact manifest')
        for name,digest in self.meta['files'].items():
            path=(directory/name).resolve()
            if directory.resolve() not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Artifact integrity failure: '+name)
        import csv
        with (DATA/'stops.txt').open() as f:stop_ids=[r['stop_id'] for r in csv.DictReader(f)]
        routes=json.loads((DATA/'manifest.json').read_text())['routes'];nodes=[]
        for r in routes:
            for reverse in (False,True):
                seq=r['stops'][::-1] if reverse else r['stops'];rid=r['route_id']+('_R' if reverse else '')
                nodes.extend([[rid,a,b] for a,b in zip(seq,seq[1:])])
        if self.meta['stops']!=stop_ids or self.meta['nodes']!=nodes:raise ValueError('Stop or segment mapping mismatch')
        self.adj=torch.tensor(np.load(directory/'adjacency.npy',allow_pickle=False))
        supports=np.load(directory/'supports.npy',allow_pickle=False)
        if self.adj.shape!=(len(stop_ids),len(stop_ids)) or not torch.isfinite(self.adj).all():raise ValueError('Invalid crowd graph')
        self.models={}
        self.models['crowd']=STGCN(**self.meta['models']['crowd']['config'])
        self.models['eta']=DCRNN(**self.meta['models']['eta']['config'],supports=supports)
        for kind,model in self.models.items():
            model.load_state_dict(torch.load(directory/(kind+'.pt'),map_location='cpu',weights_only=True),strict=True);model.eval()
        if not np.array_equal(self.models['eta'].supports.numpy(),supports):raise ValueError('Checkpoint graph differs from support file')
        with np.load(directory/'replay.npz',allow_pickle=False) as replay:
            self.replay={'crowd':replay['crowd'].copy(),'eta':replay['travel'].copy()}
        for kind,features,n in [('crowd',8,len(stop_ids)),('eta',4,len(nodes))]:
            shape=(n,features);info=self.meta['models'][kind]
            mean=np.asarray(info['mean']);std=np.asarray(info['std'])
            if mean.shape!=shape or std.shape!=shape or not np.isfinite(mean).all() or not np.isfinite(std).all() or (std<=0).any():raise ValueError('Invalid feature scalers')
            if self.replay[kind].shape!=(35,288 if kind=='crowd' else 96,n,features) or not np.isfinite(self.replay[kind]).all():raise ValueError('Invalid replay history shape')

    @lru_cache(maxsize=256)
    def predict(self,hour,minute):
        np,torch=self.np,self.torch;result={}
        for kind,model in self.models.items():
            info=self.meta['models'][kind];t=(hour*60+minute)//info['bin_minutes'];length=info['history_steps']
            if t<length:raise ValueError('Insufficient completed replay history')
            mean=np.asarray(info['mean'],np.float32);std=np.asarray(info['std'],np.float32)
            x=(self.replay[kind][34,t-length:t]-mean)/std
            with torch.inference_mode():
                raw=model(torch.tensor(x[None]),self.adj).numpy()[0] if kind=='crowd' else model(torch.tensor(x[None])).numpy()[0,0]
            values=raw*std[:,info['target_index']]+mean[:,info['target_index']]
            if not np.isfinite(values).all():raise ValueError('Nonfinite prediction')
            values=np.clip(values,0,1) if kind=='crowd' else np.maximum(values,.1)
            mapping=self.meta['stops'] if kind=='crowd' else [tuple(n) for n in self.meta['nodes']]
            result[kind]=dict(zip(mapping,values.tolist()))
        return dict(**result,mode='SYNTHETIC_TRAINED_DEEP_LEARNING',eta_model='DCRNN V2',crowd_model='ST-GCN',fallback_reason=None,history_source='Synthetic test-day 34 replay; completed bins before requested clock time',horizons=dict(eta_minutes=15,crowd_minutes=5))

@lru_cache(maxsize=1)
def get_bundle():
    # Project root may not be on sys.path when uvicorn uses --app-dir backend.
    import sys
    if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
    return ForecastBundle()

def forecast(hour,minute):
    try:
        if os.getenv('BUSSURE_DISABLE_MODELS')=='1':raise ValueError('Models disabled by BUSSURE_DISABLE_MODELS')
        return get_bundle().predict(hour,minute)
    except (ImportError,OSError,ValueError,RuntimeError,KeyError) as exc:
        from ..api.synthetic import dataset
        _,stops,model,_=dataset();eta={};crowd={s['stop_id']:[] for s in stops}
        for (rid,a,b,h),(ride,load) in model.items():
            if h==hour:
                eta[(rid,a,b)]=ride;crowd[a].append(load);crowd[b].append(load)
        return dict(eta=eta,crowd={s:sum(v)/len(v) if v else .3 for s,v in crowd.items()},mode='BASELINE_FALLBACK',eta_model='Segment/hour mean',crowd_model='Stop/hour mean occupancy',fallback_reason=str(exc),history_source='Original hourly synthetic training observations',horizons=None)
