"""Bounded SUNT adapter; reads extracted Parquet in place, exports a small subset.

Target timestamps are stop-observation proxies, not verified door events. GTFS
trip_id is a topology reference, not a recovered actual scheduled vehicle trip.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import resource
import sys
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from .artifacts import sha256, write_json

COLUMNS = ['vehicle', 'route_short_name', 'direction_id', 'gps_datetime', 'stop_id', 'service_code']
LABEL = 'AVL stop-transition proxy: last upstream observation to first downstream observation'


def peak_rss_mib():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (1024**2 if sys.platform == 'darwin' else 1024)


def selected_batches(path, route, direction, service_code, columns, batch_size=8192):
    parquet = pq.ParquetFile(path)
    if not set(columns).issubset(parquet.schema_arrow.names):
        raise ValueError(f'Missing required Parquet columns in {path}')
    offset = 0
    for batch in parquet.iter_batches(batch_size=batch_size, columns=columns, use_threads=False):
        mask = pc.and_(pc.equal(batch.column('route_short_name'), route),
                       pc.and_(pc.equal(batch.column('direction_id'), direction),
                               pc.equal(batch.column('service_code'), service_code)))
        # Original row ordinals detect interruptions by filtered-out records.
        batch = batch.append_column('_source_row', pa.array(np.arange(offset, offset+batch.num_rows, dtype=np.int64)))
        offset += batch.num_rows
        selected = batch.filter(mask)
        if selected.num_rows:
            yield selected.to_pandas()


def topology(source, route, direction, service_code, first_stop, segments):
    gtfs = source/'GTFS/BUS'
    routes = pd.read_csv(gtfs/'routes.txt', dtype=str, keep_default_na=False)
    chosen_routes = routes.loc[routes.route_short_name == route]
    if len(chosen_routes) != 1:
        raise ValueError(f'Expected one unambiguous GTFS route for {route}, found {len(chosen_routes)}')
    route_id = chosen_routes.iloc[0].route_id
    shape_id = f'{service_code}_{direction}'
    # trips.txt is 5.3 MB; even this is filtered in chunks.
    matches = []
    for chunk in pd.read_csv(gtfs/'trips.txt', dtype=str, keep_default_na=False, chunksize=8192):
        chosen = chunk[(chunk.route_id == route_id) & (chunk.shape_id == shape_id)]
        if len(chosen):
            matches.append(chosen)
    if not matches:
        raise ValueError(f'No matching GTFS shape {shape_id} for route {route_id}')
    trip = pd.concat(matches, ignore_index=True).iloc[[0]]
    trip_id = trip.iloc[0].trip_id
    times = []
    for chunk in pd.read_csv(gtfs/'stop_times.txt', dtype=str, keep_default_na=False, chunksize=8192):
        chosen = chunk[chunk.trip_id == trip_id]
        if len(chosen):
            times.append(chosen)
    if not times:
        raise ValueError('Matched GTFS template has no stop times')
    times = pd.concat(times)
    times['stop_sequence'] = times.stop_sequence.astype(int)
    times = times.sort_values('stop_sequence')
    all_stops = times.stop_id.tolist()
    chosen_times = times.iloc[first_stop:first_stop+segments+1].copy()
    stops = chosen_times.stop_id.tolist()
    if len(stops) != segments+1 or len(set(stops)) != len(stops):
        raise ValueError('Requested segment block must contain the full number of unique consecutive stops')
    # Reject repeated selected stops elsewhere in this pattern: would make direction ambiguous.
    if any(all_stops.count(stop) != 1 for stop in stops):
        raise ValueError('Selected stop occurs multiple times in the full route pattern')
    stop_table = pd.read_csv(gtfs/'stops.txt', dtype=str, keep_default_na=False)
    selected_stops = stop_table[stop_table.stop_id.isin(stops)]
    if len(selected_stops) != len(stops):
        raise ValueError('Selected GTFS stop coordinates/IDs missing')
    parent_ids = set(selected_stops.parent_station)-{''} if 'parent_station' in selected_stops else set()
    selected_stops = stop_table[stop_table.stop_id.isin(set(stops)|parent_ids)]
    agencies = pd.read_csv(gtfs/'agency.txt', dtype=str, keep_default_na=False)
    timezone = agencies.loc[agencies.agency_id == chosen_routes.iloc[0].agency_id, 'agency_timezone'].iloc[0]
    calendars = pd.read_csv(gtfs/'calendar.txt', dtype=str)
    calendar = calendars.loc[calendars.service_id == trip.iloc[0].service_id]
    return dict(route_id=route_id, trip_id=trip_id, shape_id=shape_id, stops=stops, all_stops=set(all_stops),
                routes=chosen_routes, trips=trip, stop_times=chosen_times, stop_table=selected_stops,
                calendar=calendar, timezone=timezone)


def line_matches(path, info, route, direction, service_code, batch_size):
    columns = ['route_short_name', 'direction_id', 'service_code', 'pt_sequence', 'stop_id']
    frames = list(selected_batches(path, route, direction, service_code, columns, batch_size))
    if not frames:
        return False
    frame = pd.concat(frames).dropna(subset=['stop_id']).sort_values('pt_sequence')
    sequence = frame.stop_id.astype('int64').astype(str).tolist()
    requested = info['stops']
    return any(sequence[i:i+len(requested)] == requested for i in range(len(sequence)-len(requested)+1))


def distance_m(a, b):
    lat1, lon1, lat2, lon2 = np.radians([*a, *b])
    d = np.sin((lat2-lat1)/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin((lon2-lon1)/2)**2
    return float(6371000*2*np.arcsin(np.sqrt(np.clip(d,0,1))))


def extract_day(frame, info, day, min_seconds=5, max_seconds=900, max_speed_mps=35):
    counts = Counter()
    frame = frame.dropna(subset=['vehicle','gps_datetime','stop_id']).copy()
    frame['gps_datetime'] = pd.to_datetime(frame.gps_datetime)
    # SUNT timestamps are timezone-naive. Explicitly adopt its GTFS agency timezone.
    if frame.gps_datetime.dt.tz is None:
        frame['gps_datetime'] = frame.gps_datetime.dt.tz_localize(info['timezone'], ambiguous='raise', nonexistent='raise')
    else:
        frame['gps_datetime'] = frame.gps_datetime.dt.tz_convert(info['timezone'])
    in_day = frame.gps_datetime.dt.strftime('%Y-%m-%d') == day
    counts['outside_file_date'] += int((~in_day).sum())
    frame = frame.loc[in_day].copy()
    frame['stop_id'] = frame.stop_id.astype('int64').astype(str)
    frame = frame.sort_values(['vehicle','gps_datetime','_source_row'], kind='stable')
    positions = {stop:i for i,stop in enumerate(info['stops'])}
    coords = {r.stop_id:(float(r.stop_lat),float(r.stop_lon)) for r in info['stop_table'].itertuples()}
    records = []
    for vehicle, rows in frame.groupby('vehicle', sort=False):
        anchor = None
        previous_source_row = None
        intermediate = 0
        for stop, stamp, source_row in rows[['stop_id','gps_datetime','_source_row']].itertuples(index=False, name=None):
            if previous_source_row is not None and source_row != previous_source_row+1:
                anchor = None
                intermediate = 0
                counts['source_discontinuities'] += 1
            previous_source_row = source_row
            if stop not in positions:
                if stop in info['all_stops']:
                    anchor = None  # passed another recognized GTFS stop outside the selected block
                    intermediate = 0
                else:
                    intermediate += 1  # extra AVL stop between GTFS anchors, explicitly recorded
                continue
            if anchor is None:
                anchor = (stop, stamp)
                intermediate = 0
                continue
            previous_stop, departed = anchor
            if stop == previous_stop:
                anchor = (stop, stamp)  # last observation at the upstream stop approximates departure
                intermediate = 0
                continue
            elapsed = (stamp-departed).total_seconds()
            if positions[stop] != positions[previous_stop]+1:
                counts['skipped_or_reverse_gtfs_transition'] += 1
            elif not min_seconds <= elapsed <= max_seconds:
                counts['duration_outside_bounds'] += 1
            elif distance_m(coords[previous_stop], coords[stop])/elapsed > max_speed_mps:
                counts['implausible_minimum_speed'] += 1
            else:
                records.append({'trip_id': info['trip_id'], 'from_stop_id': previous_stop, 'to_stop_id': stop,
                                'departed_at': departed.isoformat(), 'arrived_at': stamp.isoformat(),
                                'vehicle': int(vehicle), 'source_day': day,
                                'extra_non_gtfs_records': intermediate, 'label_kind': 'avl_stop_transition_proxy',
                                'trip_id_role': 'GTFS_topology_reference_only'})
                counts['accepted'] += 1
                counts['accepted_with_extra_non_gtfs_records'] += int(intermediate > 0)
            anchor = (stop, stamp)
            intermediate = 0
    return records, counts


def prepare_subset(source, output, route='1386', direction='I', service_code=12550,
                   start='2024-05-21', end='2024-06-03', segments=20, first_stop=0,
                   batch_size=8192, max_day_rows=100000):
    source, output = Path(source), Path(output)
    dates = pd.date_range(start, end, freq='D')
    if not 1 <= len(dates) <= 14 or not 1 <= segments <= 32 or not 1 <= batch_size <= 8192 or not 1 <= max_day_rows <= 100000:
        raise ValueError('Mac adapter limit: 14 days, 32 segments, 8192-row batches, 100000 retained rows/day')
    if first_stop < 0:
        raise ValueError('first_stop must be nonnegative')
    info = topology(source, route, direction, service_code, first_stop, segments)
    if info['calendar'].empty or start.replace('-','') < info['calendar'].start_date.min() or end.replace('-','') > info['calendar'].end_date.max():
        raise ValueError('Requested period is outside the selected GTFS template calendar validity')
    output.mkdir(parents=True, exist_ok=False)
    gtfs_out = output/'gtfs'
    gtfs_out.mkdir()
    for name, data in [('routes',info['routes']),('trips',info['trips']),('stops',info['stop_table']),
                       ('stop_times',info['stop_times']),('calendar',info['calendar'])]:
        data.to_csv(gtfs_out/f'{name}.txt', index=False)
    # These are tiny filtered GTFS tables, not a copy of the full feed.
    counters, per_day, sources = Counter(), [], []
    written = 0
    out_csv = output/'segment_traversals.csv'
    for stamp in dates:
        day = stamp.strftime('%Y-%m-%d')
        path, lines = source/'AVL'/f'avl-vehicles-{day}.parquet', source/'AVL'/f'avl-lines-{day}.parquet'
        if not path.is_file() or not lines.is_file():
            per_day.append({'day':day,'status':'missing_source_file'})
            continue
        if not line_matches(lines, info, route, direction, service_code, batch_size):
            per_day.append({'day':day,'status':'topology_mismatch'})
            continue
        kept, frames = 0, []
        for selected in selected_batches(path, route, direction, service_code, COLUMNS, batch_size):
            kept += len(selected)
            if kept > max_day_rows:
                raise ValueError(f'{day} exceeds retained-row RAM cap; reduce route scope')
            frames.append(selected)
        if not frames:
            per_day.append({'day':day,'status':'no_route_observations'})
            continue
        frame = pd.concat(frames, ignore_index=True)
        del frames
        records, counts = extract_day(frame, info, day)
        del frame
        unique, seen = [], set()  # timestamps are constrained to this day; no global in-memory dedup set
        for record in records:
            key = tuple(record[k] for k in ['trip_id','from_stop_id','to_stop_id','departed_at','arrived_at'])
            if key in seen:
                counts['duplicate_observation_key'] += 1
                continue
            seen.add(key); unique.append(record)
        if unique:
            pd.DataFrame(unique).to_csv(out_csv, index=False, mode='a', header=written == 0)
        written += len(unique)
        counters.update(counts)
        per_day.append({'day':day,'status':'processed','selected_gps_rows':kept,'written_traversals':len(unique),**dict(counts)})
        for p in [path,lines]:
            sources.append({'path':str(p.relative_to(source)),'bytes':p.stat().st_size,
                            'rows':pq.ParquetFile(p).metadata.num_rows,'sha256':sha256(p)})
        print(f'{day}: selected {kept} GPS rows; wrote {len(unique)} traversals', flush=True)
    if not written:
        raise ValueError('No valid real SUNT transitions; inspect mapping instead of training')
    report = {'source_directory':str(source),'dataset':'Salvador Urban Network Transportation (SUNT)',
              'route_short_name':route,'route_id':info['route_id'],'direction_id':direction,'service_code':service_code,
              'gtfs_shape_id':info['shape_id'],'topology_trip_id':info['trip_id'],
              'trip_id_role':'Topology template only; actual scheduled GTFS trip is not identified in AVL',
              'source_timezone_assumption':info['timezone'],'start':start,'end':end,'stops':info['stops'],
              'segments':segments,'target':LABEL,'target_limitations':'Sampling times do not prove actual arrival/departure; extra AVL stops between adjacent GTFS anchors may contribute dwell.',
              'thresholds':{'min_seconds':5,'max_seconds':900,'max_straight_line_speed_mps':35},
              'batch_size':batch_size,'max_retained_rows_per_day':max_day_rows,
              'rows':written,'counters':dict(counters),'per_day':per_day,'sources':sources,
              'peak_preprocessing_rss_mib':peak_rss_mib(),
              'additional_subset_bytes':sum(p.stat().st_size for p in output.rglob('*') if p.is_file())}
    report['gtfs_sources'] = {name:sha256(source/'GTFS/BUS'/name) for name in ['routes.txt','trips.txt','stops.txt','stop_times.txt','calendar.txt']}
    write_json(output/'sunt_provenance.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--route', default='1386')
    parser.add_argument('--direction', choices=['I','V'], default='I')
    parser.add_argument('--service-code', type=int, default=12550)
    parser.add_argument('--start', default='2024-05-21')
    parser.add_argument('--end', default='2024-06-03')
    parser.add_argument('--segments', type=int, default=20)
    parser.add_argument('--first-stop', type=int, default=0)
    args = parser.parse_args()
    try:
        result = prepare_subset(args.source,args.output,args.route,args.direction,args.service_code,args.start,args.end,args.segments,args.first_stop)
        print(json.dumps({k:v for k,v in result.items() if k not in ['sources','per_day','gtfs_sources']},indent=2))
    except (ValueError, FileExistsError) as exc:
        parser.exit(2,f'SUNT preprocessing: {exc}\n')
