"""Rebuild fictional Chennai GTFS and observations with a fixed random seed."""
import csv
import json
import random
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'datasets/synthetic_chennai'
STOPS = [('MAD','Madipakkam',12.965,80.198),('VEL','Velachery',12.976,80.221),('GUI','Guindy',13.007,80.211),('TNG','T Nagar',13.041,80.234),('CEN','Chennai Central',13.083,80.275),('TAM','Tambaram',12.925,80.127),('KAN','Kanchipuram',12.835,79.704)]
ROUTES = [('SYN_A',['MAD','VEL','GUI','TNG','CEN'],[8,12,10,14],12),('SYN_B',['MAD','GUI','CEN'],[18,25],20),('SYN_C',['CEN','GUI','TAM','KAN'],[25,30,65],30)]

def write(name, fields, rows):
    with (OUT/name).open('w',newline='') as f:
        w=csv.writer(f); w.writerow(fields); w.writerows(rows)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'SAMPLE').write_text('Entirely synthetic services. Approximate place anchors; no official operator data.\n')
    write('stops.txt',['stop_id','stop_name','stop_lat','stop_lon'],STOPS)
    routes=[]; trips=[]; times=[]; observations=[]; buses=[]; shapes=[]
    coordinates={s[0]:(s[2],s[3]) for s in STOPS}
    rng=random.Random(42)
    for route,stops,durations,headway in ROUTES:
        for reverse in (False,True):
            rid=route+('_R' if reverse else '')
            seq=list(reversed(stops)) if reverse else stops
            mins=list(reversed(durations)) if reverse else durations
            routes.append([rid,rid,'Synthetic '+rid,3])
            shape=[]
            for a,b in zip(seq,seq[1:]):
                lat,lon=coordinates[a];endlat,endlon=coordinates[b]
                for n in range(10):
                    f=n/10;curve=math.sin(math.pi*f)*.0004
                    shape.append([lat+(endlat-lat)*f+curve,lon+(endlon-lon)*f-curve])
            shape.append(list(coordinates[seq[-1]]))
            shapes.extend([[rid,p[0],p[1],i] for i,p in enumerate(shape)])
            for departure in range(360,1320,headway):
                tid=f'{rid}_{departure}'; trips.append([rid,'SYN_DAILY',tid,rid]); clock=departure
                for i,stop in enumerate(seq):
                    stamp=f'{clock//60:02}:{clock%60:02}:00'; times.append([tid,stamp,stamp,stop,i+1])
                    if i<len(mins): clock+=mins[i]
            buses.append(dict(bus_id='SIM_'+rid,route_id=rid,trip_id=f'{rid}_360',speed_mps=7,start_progress=0.1))
            for day in range(35):
                for hour in range(6,22):
                    peak=hour in (8,9,17,18,19)
                    for i,base in enumerate(mins):
                        ride=round(base*(1.3 if peak else 1)*rng.uniform(.9,1.1),2)
                        load=round(min(.98,max(.05,(.78 if peak else .35)+(0.1 if route=='SYN_A' else -.1)+rng.uniform(-.12,.12))),3)
                        observations.append([day,rid,seq[i],seq[i+1],hour,base,ride,load])
    write('routes.txt',['route_id','route_short_name','route_long_name','route_type'],routes)
    write('trips.txt',['route_id','service_id','trip_id','shape_id'],trips)
    write('shapes.txt',['shape_id','shape_pt_lat','shape_pt_lon','shape_pt_sequence'],shapes)
    write('stop_times.txt',['trip_id','arrival_time','departure_time','stop_id','stop_sequence'],times)
    write('observations.csv',['day','route_id','from_stop','to_stop','hour','scheduled_minutes','ride_minutes','occupancy_ratio'],observations)
    write('calendar.txt',['service_id','monday','tuesday','wednesday','thursday','friday','saturday','sunday','start_date','end_date'],[['SYN_DAILY',1,1,1,1,1,1,1,'20260101','20271231']])
    metadata=dict(data_source='SYNTHETIC',seed=42,days=35,training_days=28,observations=len(observations),warning='Generated data and approximate anchors. No real service or prediction accuracy claims.',routes=[dict(route_id=r[0],stops=r[1],minutes=r[2],headway=r[3]) for r in ROUTES])
    (OUT/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (OUT/'simulator.json').write_text(json.dumps(dict(label='SYNTHETIC ONLY',gtfs_directory=".",interval_seconds=2,dwell_seconds=6,buses=buses),indent=2)+'\n')
    print(f'Generated {len(routes)} routes, {len(trips)} trips, {len(observations)} observations in {OUT}')

if __name__=='__main__': main()
