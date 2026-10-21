"""Choose the longest supported contiguous chain using TRAIN coverage only."""
import argparse
import json
from pathlib import Path
import pandas as pd
import numpy as np
from .artifacts import write_json, sha256
from .train import prepare
from .preprocess import aggregate


def select_connected(subset, output, config):
    subset, output = Path(subset), Path(output)
    provenance = json.loads((subset/'sunt_provenance.json').read_text())
    if provenance['rows'] > 100000:
        raise ValueError('Connected selection is limited to 100000 derived observations on the Mac')
    data = prepare(subset/'segment_traversals.csv',subset/'gtfs',config)
    eligible = set(data['nodes'])
    stops = provenance['stops']
    best, current = [], []
    for i,(a,b) in enumerate(zip(stops,stops[1:])):
        if (provenance['route_id'],a,b) in eligible:
            current.append(i)
            if len(current)>len(best):
                best=current.copy()
        else:
            current=[]
    if not best:
        raise ValueError('No supported connected segment chain')
    chosen_stops=stops[best[0]:best[-1]+2]
    pairs=set(zip(chosen_stops,chosen_stops[1:]))
    output.mkdir(parents=True,exist_ok=False)
    (output/'gtfs').mkdir()
    frame=pd.read_csv(subset/'segment_traversals.csv',dtype={'from_stop_id':str,'to_stop_id':str})
    selected=frame[[pair in pairs for pair in zip(frame.from_stop_id,frame.to_stop_id)]]
    selected.to_csv(output/'segment_traversals.csv',index=False)
    for filename in ['routes.txt','trips.txt','calendar.txt','stops.txt','stop_times.txt']:
        table=pd.read_csv(subset/'gtfs'/filename,dtype=str,keep_default_na=False)
        if filename=='stop_times.txt':
            table=table[table.stop_id.isin(chosen_stops)]
        if filename=='stops.txt':
            parents=set(table.loc[table.stop_id.isin(chosen_stops),'parent_station'])-{''} if 'parent_station' in table else set()
            table=table[table.stop_id.isin(set(chosen_stops)|parents)]
        table.to_csv(output/'gtfs'/filename,index=False)
    provenance.update(candidate_report_sha256=sha256(subset/'sunt_provenance.json'),
        candidate_rows=provenance['rows'],candidate_segments=provenance['segments'],
        selection_method='Longest contiguous chain eligible from observed TRAIN bins only; earliest chain wins ties',
        selection_train_fraction=config['train_fraction'],selection_min_train_observations=config['min_train_observations_per_node'],
        selection_validation_start=data['report']['validation_start'],
        selected_candidate_edge_indices=best,rows=len(selected),segments=len(best),stops=chosen_stops,
        counters_scope='Counters and per_day describe the 20-segment candidate extraction before connected selection')
    # Filtering can shift the first/last populated bin. Recheck selection using
    # the FINAL training cutoff, so no validation labels choose the graph.
    final=prepare(output/'segment_traversals.csv',output/'gtfs',config)
    candidates=sorted(set(data['frame'].node))
    grid,values=aggregate(data['frame'],candidates,config['bin_minutes'])
    final_cutoff=pd.Timestamp(final['report']['validation_start'])
    valid=np.isfinite(values[grid<final_cutoff]).sum(0)>=config['min_train_observations_per_node']
    final_eligible={n for n,keep in zip(candidates,valid) if keep}
    final_best,current=[],[]
    for i,(a,b) in enumerate(zip(stops,stops[1:])):
        if (provenance['route_id'],a,b) in final_eligible:
            current.append(i)
            if len(current)>len(final_best): final_best=current.copy()
        else:
            current=[]
    if final_best!=best:
        raise ValueError('Final cutoff changes connected selection; reconcile this before training')
    provenance['selection_validation_start']=final['report']['validation_start']
    provenance['final_cutoff_selection_rechecked']=True
    if len(final['nodes'])!=len(best) or int(final['adjacency'].sum())!=len(best)-1:
        raise ValueError('Final training graph is not the selected connected chain')
    write_json(output/'sunt_provenance.json',provenance)
    return final['report']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subset',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--config',default=str(Path(__file__).with_name('sunt_dev_config.json')))
    args=parser.parse_args()
    try:
        print(json.dumps(select_connected(args.subset,args.output,json.loads(Path(args.config).read_text())),indent=2))
    except (ValueError,FileExistsError) as exc:
        parser.exit(2,f'SUNT connected selection: {exc}\n')
