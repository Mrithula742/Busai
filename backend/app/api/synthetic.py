"""End-to-end synthetic experiment. Empirical baselines, not DCRNN/ST-GCN."""
import csv
import json
from collections import defaultdict
from functools import lru_cache
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..config import ROOT

router = APIRouter(prefix='/api/synthetic', tags=['Synthetic experiment'])
DIRECTORY = ROOT / 'datasets/synthetic_chennai'

@lru_cache(maxsize=1)
def dataset():
    try:
        manifest=json.loads((DIRECTORY/'manifest.json').read_text())
        with (DIRECTORY/'stops.txt').open() as f: stops=list(csv.DictReader(f))
        with (DIRECTORY/'observations.csv').open() as f: rows=list(csv.DictReader(f))
    except (OSError, ValueError) as exc:
        raise HTTPException(503,'Generate the dataset: .venv/bin/python scripts/generate_synthetic.py') from exc
    buckets=defaultdict(list)
    key=lambda r:(r['route_id'],r['from_stop'],r['to_stop'],int(r['hour']))
    for row in rows:
        if int(row['day'])<28: buckets[key(row)].append(row)
    model={k:tuple(sum(float(r[field]) for r in values)/len(values) for field in ('ride_minutes','occupancy_ratio')) for k,values in buckets.items()}
    test=[r for r in rows if int(r['day'])>=28]
    metrics={field:round(sum(abs(float(r[target])-model[key(r)][i]) for r in test)/len(test),4) for field,target,i in [('ride_mae_minutes','ride_minutes',0),('occupancy_mae_ratio','occupancy_ratio',1)]}
    return manifest,stops,model,dict(model='Training-set segment/hour means',training_rows=len(rows)-len(test),test_rows=len(test),split='Days 0–27 train; days 28–34 held out',**metrics)

@router.get('/catalog')
def catalog():
    manifest,stops,_,evaluation=dataset()
    return dict(data_source='SYNTHETIC',warning=manifest['warning'],stops=stops,routes=[dict(route_id=r['route_id']+suffix) for r in manifest['routes'] for suffix in ('','_R')],evaluation=evaluation)

class Plan(BaseModel):
    origin: str = Field(min_length=1,max_length=100)
    destination: str = Field(min_length=1,max_length=100)
    hour: int = Field(default=8,ge=6,le=21)
    minute: int = Field(default=0,ge=0,le=59)
    preference: Literal['faster','less_crowd','less_delay']='faster'

@router.post('/journey')
def journey(body: Plan):
    manifest,stops,model,evaluation=dataset()
    lookup={s['stop_id']:s for s in stops}
    def resolve(value):
        found=next((s['stop_id'] for s in stops if value.strip().casefold() in (s['stop_id'].casefold(),s['stop_name'].casefold())),None)
        if not found: raise HTTPException(422,'Unknown stop. Choose a stop from the synthetic catalog.')
        return found
    origin,destination=resolve(body.origin),resolve(body.destination)
    if origin==destination: raise HTTPException(422,'Choose different origin and destination stops.')
    options=[]
    for route in manifest['routes']:
        for reverse in (False,True):
            rid=route['route_id']+('_R' if reverse else '')
            seq=list(reversed(route['stops'])) if reverse else route['stops']
            base=list(reversed(route['minutes'])) if reverse else route['minutes']
            if origin not in seq or destination not in seq or seq.index(origin)>=seq.index(destination): continue
            a,b=seq.index(origin),seq.index(destination)
            predictions=[model[(rid,seq[i],seq[i+1],body.hour)] for i in range(a,b)]
            ride=sum(p[0] for p in predictions); scheduled=sum(base[a:b]); delay=max(0,ride-scheduled)
            # Timetable departures repeat from 06:00; include time to the boarding stop.
            clock=body.hour*60+body.minute
            offset=sum(base[:a]); wait=(360+offset-clock)%route['headway']
            last=360+((1319-360)//route['headway'])*route['headway']+offset
            if clock+wait>last: continue
            occupancy=sum(p[1] for p in predictions)/len(predictions)
            options.append(dict(route_id=rid,stops=[lookup[s]['stop_name'] for s in seq[a:b+1]],points=[[float(lookup[s]['stop_lat']),float(lookup[s]['stop_lon'])] for s in seq[a:b+1]],ride_minutes=round(ride,1),delay_minutes=round(delay,1),wait_minutes=wait,walking_minutes=0,total_minutes=round(ride+wait,1),occupancy_ratio=round(occupancy,3),crowd_level='HIGH' if occupancy>=.7 else 'MODERATE' if occupancy>=.4 else 'LOW',metrics_source='SYNTHETIC_EMPIRICAL_BASELINE'))
    key={'faster':'total_minutes','less_crowd':'occupancy_ratio','less_delay':'delay_minutes'}[body.preference]
    options.sort(key=lambda r:(r[key],r['total_minutes'],r['route_id']))
    return dict(data_source='SYNTHETIC',warning=manifest['warning'],routes=options,recommended_route_id=options[0]['route_id'] if options else None,evaluation=evaluation,answer=f"{len(options)} synthetic direct options. Ride includes predicted delay; total = ride + scheduled wait. Origin is the selected stop (zero walking)." if options else 'No direct synthetic service at this time. Try another pair or departure time; transfers are not supported.')
