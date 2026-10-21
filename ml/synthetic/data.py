"""Seeded full-day simulation; no measured operational observations."""
import csv
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'datasets/synthetic_chennai'
FEATURES=['boarding_ratio','alighting_ratio','occupancy_ratio','hour_sin','hour_cos','dow_sin','dow_cos','is_weekend']
ETA_FEATURES=['travel_minutes','observed','hour_sin','hour_cos']

def generate():
    manifest=json.loads((DATA/'manifest.json').read_text())
    with (DATA/'stops.txt').open() as f: stops=list(csv.DictReader(f))
    stop_ids=[s['stop_id'] for s in stops]; nodes=[]; edges=[]; base=[]
    adjacency=np.eye(len(stops),dtype=np.float32)
    for route in manifest['routes']:
        for reverse in (False,True):
            rid=route['route_id']+('_R' if reverse else '')
            seq=route['stops'][::-1] if reverse else route['stops']
            durations=route['minutes'][::-1] if reverse else route['minutes']
            pairs=[(rid,a,b) for a,b in zip(seq,seq[1:])]
            nodes+=pairs; base+=durations; edges+=list(zip(pairs,pairs[1:]))
            for a,b in zip(seq,seq[1:]):
                i,j=stop_ids.index(a),stop_ids.index(b);adjacency[i,j]=adjacency[j,i]=1
    degree=adjacency.sum(1)
    adjacency=adjacency/np.sqrt(degree[:,None]*degree[None,:])
    from ml.travel_time.dcrnn_v2.graph import build_graph
    _,supports=build_graph(nodes,edges)
    rng=np.random.default_rng(42)
    crowd=np.zeros((35,288,len(stops),8),np.float32)
    travel=np.zeros((35,96,len(nodes),4),np.float32)
    for day in range(35):
        previous=np.full(len(stops),.25)
        travel_previous=np.array(base,dtype=float)
        for t in range(288):
            hour=t/12
            demand=.25+.5*np.exp(-((hour-8.5)/1.5)**2)+.45*np.exp(-((hour-18)/1.7)**2)
            target=np.clip(demand+np.linspace(-.07,.07,len(stops)),.05,.95)
            occupancy=np.clip(.78*previous+.22*target+rng.normal(0,.015,len(stops)),.02,.98)
            board=np.maximum(occupancy-previous,0)+.04
            alight=np.maximum(previous-occupancy,0)+.04
            crowd[day,t,:,0]=board;crowd[day,t,:,1]=alight;crowd[day,t,:,2]=occupancy
            crowd[day,t,:,3:]=[np.sin(hour*np.pi/12),np.cos(hour*np.pi/12),np.sin((day%7)*2*np.pi/7),np.cos((day%7)*2*np.pi/7),float(day%7>=5)]
            previous=occupancy
            if t%3==0:
                target_time=np.array(base)*(1+.35*max(0,demand-.3))
                values=.7*travel_previous+.3*target_time+rng.normal(0,.03,len(nodes))*np.array(base)
                travel[day,t//3,:,0]=values;travel[day,t//3,:,1]=1
                travel[day,t//3,:,2:]=[np.sin(hour*np.pi/12),np.cos(hour*np.pi/12)]
                travel_previous=values
    return dict(crowd=crowd,travel=travel,adjacency=adjacency,supports=supports,stops=stop_ids,nodes=[list(n) for n in nodes])

def windows(array,length,start,end):
    x=[];y=[]
    for day in range(start,end):
        for t in range(length,array.shape[1]):
            x.append(array[day,t-length:t]);y.append(array[day,t,:,2 if length==12 else 0])
    return np.asarray(x,dtype=np.float32),np.asarray(y,dtype=np.float32)
