"""Reproducible CPU training; select on validation days, evaluate test once."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import numpy as np
import torch
from ml.synthetic.data import generate,windows,DATA,FEATURES,ETA_FEATURES
from ml.synthetic.models import STGCN
from ml.travel_time.dcrnn_v2.model import DCRNN

OUT=Path(__file__).with_name('artifacts')

def train(epochs=18,output_dir=None):
    directory=Path(output_dir) if output_dir is not None else OUT
    random.seed(42);np.random.seed(42);torch.manual_seed(42);torch.set_num_threads(2)
    bundle=generate();directory.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(directory/'replay.npz',crowd=bundle['crowd'],travel=bundle['travel'])
    meta=dict(schema_version=1,training_data='SYNTHETIC_CHENNAI_V2',seed=42,split=dict(train=[0,21],validation=[21,28],test=[28,35]),stops=bundle['stops'],nodes=bundle['nodes'],features=dict(crowd=FEATURES,eta=ETA_FEATURES),models={},warning='Synthetic replay forecasts; no real-world validation. Test day 34 replay is used by the application.')
    for kind,array,length in [('crowd',bundle['crowd'],12),('eta',bundle['travel'],4)]:
        mean=array[:21].mean(axis=(0,1));std=array[:21].std(axis=(0,1));std=np.maximum(std,1e-4)
        # Scale only measured features, preserve cyclical inputs and observation flags.
        scale_indices=[0,1,2] if kind=='crowd' else [0]
        mask=[i for i in range(array.shape[-1]) if i not in scale_indices]
        mean[:,mask]=0;std[:,mask]=1
        scaled=(array-mean)/std
        xs,ys=windows(scaled,length,0,21);xv,yv=windows(scaled,length,21,28);xt,yt=windows(scaled,length,28,35)
        target=2 if kind=='crowd' else 0
        adj=torch.tensor(bundle['adjacency'])
        config=dict(num_nodes=len(bundle['nodes']),input_dim=4,hidden_dim=16,num_layers=2,diffusion_steps=2,dropout=0,sequence_length=4,prediction_horizon=1)
        model=STGCN(len(bundle['stops'])) if kind=='crowd' else DCRNN(**config,supports=bundle['supports'])
        def forward(x):return model(x,adj) if kind=='crowd' else model(x)[:,0]
        optimizer=torch.optim.Adam(model.parameters(),lr=.003)
        best=float('inf');history=[]
        for epoch in range(epochs):
            model.train();order=np.random.permutation(len(xs))
            for start in range(0,len(order),128):
                ids=order[start:start+128];pred=forward(torch.tensor(xs[ids]));loss=(pred-torch.tensor(ys[ids])).abs().mean()
                optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);optimizer.step()
            model.eval()
            with torch.no_grad():
                val=np.concatenate([forward(torch.tensor(xv[i:i+256])).numpy() for i in range(0,len(xv),256)])
            mae=float(np.mean(np.abs(val-yv)*std[:,target]));history.append(mae)
            if mae<best:
                best=mae;torch.save(model.state_dict(),directory/(kind+'.pt'))
        model.load_state_dict(torch.load(directory/(kind+'.pt'),map_location='cpu',weights_only=True),strict=True)
        model.eval()
        with torch.no_grad():pred=np.concatenate([forward(torch.tensor(xt[i:i+256])).numpy() for i in range(0,len(xt),256)])
        actual=yt*std[:,target]+mean[:,target];pred=pred*std[:,target]+mean[:,target]
        pred=np.clip(pred,0,1) if kind=='crowd' else np.maximum(pred,0)
        baseline=xt[:,-1,:,target]*std[:,target]+mean[:,target]
        info=dict(architecture='ST-GCN (new synthetic implementation)' if kind=='crowd' else 'DCRNN V2 (existing DCGRU implementation)',config=dict(nodes=len(bundle['stops']),features=8,hidden=32) if kind=='crowd' else config,history_steps=length,bin_minutes=5 if kind=='crowd' else 15,prediction_horizon_steps=1,mean=mean.tolist(),std=std.tolist(),target_index=target,train_windows=len(xs),validation_windows=len(xv),test_windows=len(xt),epochs=epochs,best_validation_mae=best,test_mae=float(np.mean(abs(pred-actual))),test_rmse=float(np.sqrt(np.mean((pred-actual)**2))),persistence_test_mae=float(np.mean(abs(baseline-actual))),units='occupancy ratio (0–1)' if kind=='crowd' else 'minutes per segment',validation_history=history)
        meta['models'][kind]=info
        print(kind,info['test_mae'],info['persistence_test_mae'],flush=True)
    np.save(directory/'adjacency.npy',bundle['adjacency']);np.save(directory/'supports.npy',bundle['supports'])
    meta['source_sha256']={str(p.relative_to(Path(__file__).resolve().parents[2])):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('data.py'),Path(__file__).with_name('models.py'),Path(__file__).resolve().parents[1]/'travel_time/dcrnn_v2/model.py']}
    meta['gtfs_sha256']={name:hashlib.sha256((DATA/name).read_bytes()).hexdigest() for name in ['stops.txt','routes.txt','trips.txt','stop_times.txt','shapes.txt','calendar.txt']}
    meta['dataset_sha256']=hashlib.sha256((DATA/'manifest.json').read_bytes()).hexdigest()
    meta['files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file() and p.name!='manifest.json'}
    (directory/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    return meta

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--epochs',type=int,default=18);args=p.parse_args();train(args.epochs)
