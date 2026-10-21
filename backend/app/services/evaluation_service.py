"""Re-evaluate existing weights on held-out histories; never train or alter artifacts."""
from functools import lru_cache
from .forecast_service import get_bundle

@lru_cache(maxsize=2)
def evaluation(kind):
    import numpy as np
    import torch
    from ml.synthetic.data import windows
    b=get_bundle();info=b.meta['models'][kind]
    mean=np.asarray(info['mean'],np.float32);std=np.asarray(info['std'],np.float32)
    raw=b.replay[kind];x,y=windows((raw-mean)/std,info['history_steps'],28,35)
    model=b.models[kind]
    with torch.inference_mode():
        preds=np.concatenate([(model(torch.tensor(x[i:i+128]),b.adj).numpy() if kind=='crowd' else model(torch.tensor(x[i:i+128])).numpy()[:,0]) for i in range(0,len(x),128)])
    target=info['target_index'];actual=y*std[:,target]+mean[:,target]
    predicted=preds*std[:,target]+mean[:,target]
    predicted=np.clip(predicted,0,1) if kind=='crowd' else np.maximum(predicted,0)
    baseline=x[:,-1,:,target]*std[:,target]+mean[:,target]
    metrics=lambda p:dict(mae=float(np.abs(p-actual).mean()),rmse=float(np.sqrt(((p-actual)**2).mean())))
    ids=b.meta['stops'] if kind=='crowd' else [':'.join(n) for n in b.meta['nodes']]
    indices=np.linspace(0,len(x)-1,64,dtype=int)
    slots=raw.shape[1]-info['history_steps']
    series=[]
    for n,node in enumerate(ids):
        series.append(dict(node_id=node,points=[dict(index=int(i),day=28+int(i)//slots,minute_of_day=(int(i)%slots+info['history_steps'])*info['bin_minutes'],actual=float(actual[i,n]),predicted=float(predicted[i,n]),baseline=float(baseline[i,n])) for i in indices]))
    return dict(source='HELD_OUT_SYNTHETIC_EVALUATION',model=info['architecture'],kind=kind,units=info['units'],split='Days 28–34; never used for model selection',test_windows=len(x),node_count=len(ids),metrics=metrics(predicted),baseline_metrics=metrics(baseline),baseline='Persistence: last observed target',series=series,sampling='64 evenly spaced test windows per node for display; metrics use every test window and node',horizon_minutes=info['bin_minutes'],runtime_prediction=False)
