"""Bounded, time-dependent itinerary search on the active synthetic network."""
import math
from datetime import datetime,timedelta,timezone
from ..utils.geo import haversine_meters
from ..utils.time_utils import utc_now
from .disruption_service import impact
IST=timezone(timedelta(hours=5,minutes=30))


def reliability(delay,transfers,buffer_minutes,events,tracking):
    """A deterministic planning index, never a probability of on-time arrival."""
    penalties=dict(delay=min(35,delay*1.5),transfers=transfers*8,transfer_buffer=transfers*max(0,5-buffer_minutes)*3,disruption=min(25,len(set(events))*8),tracking=0 if tracking else 5)
    return round(max(0,100-sum(penalties.values())),1),{k:round(v,2) for k,v in penalties.items()}

class AIJourneyService:
    def __init__(self,gtfs,store,events):
        self.gtfs,self.store,self.events=gtfs,store,events
        self.patterns=[]
        for rid,trips in gtfs.route_trips.items():
            seen=set()
            for tid in trips:
                seq=gtfs.trip_stops[tid];ids=tuple(r['stop_id'] for r in seq)
                if ids not in seen:self.patterns.append((rid,ids));seen.add(ids)

    def effect(self,rid,when,trip,segment,duration=0):
        parts=segment.split(':');a,b=self.gtfs.stops[parts[-2]],self.gtfs.stops[parts[-1]]
        return impact(self.events,rid,when,trip,segment,[[a['latitude'],a['longitude']],[b['latitude'],b['longitude']]],until=when+timedelta(minutes=duration) if duration else None)

    def next_trip(self,rid,stop,ready,date,forecast):
        choices=[]
        for tid in self.gtfs.route_trips[rid]:
            service=self.gtfs.trips[tid]['service_id']
            calendars=[r for r in self.gtfs.calendar if r['service_id']==service]
            allowed=not calendars
            for c in calendars:
                allowed=c['start_date']<=date.strftime('%Y%m%d')<=c['end_date'] and c[date.strftime('%A').lower()]=='1'
            for c in self.gtfs.calendar_dates:
                if c['service_id']==service and c['date']==date.strftime('%Y%m%d'):allowed=c['exception_type']=='1'
            if not allowed:continue
            row=next((r for r in self.gtfs.trip_stops[tid] if r['stop_id']==stop),None)
            if row is None or row.get('pickup_type')=='1':continue
            value=row['departure_time'] or row['arrival_time']
            if not value:continue
            h,m,s=map(int,value.split(':'));departure=h*60+m+s/60
            seq=self.gtfs.trip_stops[tid];index=next(i for i,r in enumerate(seq) if r['stop_id']==stop)
            extra=0;blocked=False
            for i in range(index):
                a,b=seq[i]['stop_id'],seq[i+1]['stop_id']
                value=seq[i]['departure_time'] or seq[i]['arrival_time'];hh,mm,ss=map(int,value.split(':'))
                when=datetime.combine(date,datetime.min.time(),tzinfo=IST)+timedelta(minutes=hh*60+mm+ss/60+extra)
                effect=self.effect(rid,when,tid,f'{rid}:{a}:{b}',forecast['eta'].get((rid,a,b),0))
                if effect['blocked']:blocked=True;break
                extra+=forecast['eta'].get((rid,a,b),0)*(effect['factor']-1)
            if not blocked and departure+extra+1e-6>=ready:choices.append((departure+extra,tid))
        return min(choices) if choices else None

    def live_arrival(self,rid,seq,boarding,forecast,ready,date):
        now=utc_now();clock=now.astimezone(IST);midnight=datetime.combine(date,datetime.min.time(),tzinfo=IST)
        if abs((midnight+timedelta(minutes=ready)-now).total_seconds())>900:return None
        candidates=[]
        for bus in self.store.list():
            if bus.route_id!=rid or not bus.route_verified or bus.status=='STALE' or (now-bus.timestamp).total_seconds()>=self.store.stale_seconds:continue
            current=bus.current_stop_id
            if current not in seq:continue
            i=seq.index(current)
            if i>boarding:continue
            if i==boarding:
                s=self.gtfs.stops[seq[i]]
                if haversine_meters(bus.latitude,bus.longitude,s['latitude'],s['longitude'])>40:continue
                remaining=0
            else:
                a,b=self.gtfs.stops[seq[i]],self.gtfs.stops[seq[i+1]]
                full=haversine_meters(a['latitude'],a['longitude'],b['latitude'],b['longitude'])
                distance=haversine_meters(bus.latitude,bus.longitude,b['latitude'],b['longitude'])
                # Only plausible on-segment fixes are used. No road map matching claim.
                if distance>full*1.2 or (bus.accuracy_meters is not None and bus.accuracy_meters>100):continue
                remaining=forecast['eta'][(rid,seq[i],seq[i+1])]*min(1,distance/full)
                for j in range(i+1,boarding):remaining+=forecast['eta'][(rid,seq[j],seq[j+1])]+.5
            arrival=(now-midnight).total_seconds()/60+remaining
            if arrival+1e-6<ready:continue
            affected=False
            for j in range(i,boarding):
                effect=self.effect(rid,now,bus.trip_id,f'{rid}:{seq[j]}:{seq[j+1]}')
                if effect['blocked']:affected=True
                remaining+=forecast['eta'][(rid,seq[j],seq[j+1])]*(effect['factor']-1)
            if affected:continue
            arrival=(now-midnight).total_seconds()/60+remaining
            candidates.append((arrival,bus))
        return min(candidates,key=lambda p:(p[0],p[1].bus_id)) if candidates else None

    def search(self,body,forecast):
        stops=self.gtfs.stops
        def resolve(value):
            sid=next((sid for sid,s in stops.items() if value.strip().casefold() in (sid.casefold(),s['stop_name'].casefold())),None)
            if sid is None:raise ValueError('Unknown stop; choose a catalog stop')
            return sid
        dest=resolve(body.destination)
        departure=body.departure_time.astimezone(IST)
        start=departure.hour*60+departure.minute+departure.second/60
        if departure.hour<6 or departure.hour>21:raise ValueError('Synthetic departures must be between 06:00 and 21:59 IST')
        date=departure.date();midnight=datetime.combine(date,datetime.min.time(),tzinfo=IST)
        origins=[]
        if body.latitude is not None:
            for sid,s in stops.items():
                d=haversine_meters(body.latitude,body.longitude,s['latitude'],s['longitude'])
                if d<=body.walking_radius:origins.append((sid,d/84,d))
            origins.sort(key=lambda v:v[1]);origins=origins[:5]
        else:origins=[(resolve(body.origin),0,0)]
        if origins and origins[0][0]==dest and body.latitude is None:raise ValueError('Choose different origin and destination stops')
        options=[];expanded=0
        def visit(sid,clock,legs,steps,visited,used,walking,delay,crowd,events):
            nonlocal expanded
            expanded+=1
            if expanded>5000:return
            if sid==dest and legs:
                transfers=len(legs)-1;tracked=any(leg.get('bus') for leg in legs)
                score,penalties=reliability(delay,transfers,body.transfer_buffer,events,tracked)
                wait=sum(leg['wait_minutes'] for leg in legs)
                points=[[stops[s]['latitude'],stops[s]['longitude']] for leg in legs for s in leg['stop_ids']]
                total=clock-start
                option_id='|'.join(f"{l['route_id']}:{l['stop_ids'][0]}:{l['stop_ids'][-1]}" for l in legs)
                reasons=[f"{transfers} transfers; {round(wait,1)} min waiting; {round(walking,1)} min approximate walking",f"{forecast['eta_model']} travel forecast and {forecast['crowd_model']} stop occupancy forecast",f"Reliability index {score}/100 uses documented penalties; it is not an on-time probability"]
                if events:reasons.append('Affected by synthetic disruptions: '+', '.join(sorted(set(events))))
                if 7<=departure.hour<=9 or 17<=departure.hour<=19:reasons.append('Peak-hour replay conditions')
                options.append(dict(option_id=option_id,route_id=' → '.join(l['route_id'] for l in legs),legs=legs,itinerary=steps,stops=[stops[s]['stop_name'] for leg in legs for s in leg['stop_ids']],points=points,total_minutes=round(total,1),arrival_time=(midnight+timedelta(minutes=clock)).isoformat(),wait_minutes=round(wait,1),walking_minutes=round(walking,1),ride_minutes=round(sum(l['ride_minutes'] for l in legs),1),delay_minutes=round(delay,1),occupancy_ratio=round(crowd,3),crowd_level='HIGH' if crowd>=.7 else 'MEDIUM' if crowd>=.4 else 'LOW',transfers=transfers,reliability_score=score,reliability_penalties=penalties,delay_risk='HIGH' if delay>15 else 'MEDIUM' if delay>5 else 'LOW',transfer_risk='NONE' if not transfers else 'HIGH' if body.transfer_buffer<5 else 'MEDIUM',duration_range_minutes=[round(total,1),round(total+sum(l['ride_minutes'] for l in legs)*.2+transfers*body.transfer_buffer,1)],range_assumption='Scenario range: nominal to nominal + 20% ride + one extra transfer buffer per transfer; not a statistical interval',explanations=reasons,disruption_ids=sorted(set(events))))
                return
            if len(legs)>=body.max_transfers+1:return
            boarding=[(sid,0,0)]
            if legs:
                for other,s in stops.items():
                    if other==sid or other in visited:continue
                    d=haversine_meters(stops[sid]['latitude'],stops[sid]['longitude'],s['latitude'],s['longitude'])
                    if d<=body.transfer_walk_radius:boarding.append((other,d/84,d))
            for board,walk,meters in boarding:
                buffer=body.transfer_buffer if legs else 0
                ready=clock+walk+buffer
                for rid,seq in self.patterns:
                    if rid in used or board not in seq:continue
                    a=seq.index(board)
                    if a==len(seq)-1:continue
                    scheduled=self.next_trip(rid,board,ready,date,forecast)
                    tracked=self.live_arrival(rid,seq,a,forecast,ready,date)
                    chosen=None
                    if scheduled:chosen=(scheduled[0],scheduled[1],None)
                    if tracked and (not chosen or tracked[0]<chosen[0]):chosen=(tracked[0],tracked[1].trip_id,tracked[1])
                    if not chosen:continue
                    depart,trip,bus=chosen;elapsed=0;route_events=[];route_delay=0;load=0
                    for b in range(a+1,len(seq)):
                        target=seq[b]
                        if target in visited:break
                        origin=seq[b-1];segment=(rid,origin,target)
                        if segment not in forecast['eta']:break
                        as_of=midnight+timedelta(minutes=depart+elapsed)
                        estimate=forecast['eta'][segment]
                        effect=self.effect(rid,as_of,trip,f'{rid}:{origin}:{target}',estimate+.5)
                        if effect['blocked']:break
                        moving=estimate*effect['factor'];elapsed+=moving+.5
                        original=self.gtfs.trip_stops[trip]
                        before=next((r for r in original if r['stop_id']==origin),None);after=next((r for r in original if r['stop_id']==target),None)
                        def minutes(row):
                            value=row['arrival_time'] or row['departure_time'];h,m,s=map(int,value.split(':'));return h*60+m+s/60
                        base=minutes(after)-minutes(before) if before and after else estimate
                        route_delay+=max(0,moving-base);route_events+=effect['events']
                        load=max(load,min(1,forecast['crowd'][target]*forecast.get('scenario_demand',{}).get(rid,1)+effect['crowd_add']))
                        finish=depart+elapsed
                        # Drop-off restrictions are checked on the chosen trip.
                        if after and after.get('drop_off_type')=='1':continue
                        bus_data=dict(bus_id=bus.bus_id,source=bus.source,timestamp=bus.timestamp.isoformat(),status=bus.status) if bus else None
                        shape=self.gtfs.get_trip_shape(trip)
                        geometry=[]
                        if shape:
                            first=next((i for i,p in enumerate(shape) if haversine_meters(*p,stops[board]['latitude'],stops[board]['longitude'])<1),None)
                            last=next((i for i,p in enumerate(shape) if first is not None and i>first and haversine_meters(*p,stops[target]['latitude'],stops[target]['longitude'])<1),None)
                            if first is not None and last is not None:geometry=shape[first:last+1]
                        leg=dict(geometry=geometry,route_id=rid,trip_id=trip,stop_ids=list(seq[a:b+1]),boarding_stop=stops[board]['stop_name'],alighting_stop=stops[target]['stop_name'],departure_time=(midnight+timedelta(minutes=depart)).isoformat(),arrival_time=(midnight+timedelta(minutes=finish)).isoformat(),wait_minutes=round(depart-clock-walk,3),ride_minutes=round(elapsed,3),bus=bus_data,wait_source='GPS_REMAINING_SEGMENT_ESTIMATE' if bus else 'SYNTHETIC_TIMETABLE',transfer_buffer_minutes=buffer)
                        newsteps=list(steps)
                        if walk:newsteps.append(dict(type='TRANSFER_WALK',minutes=round(walk,2),distance_meters=round(meters),instruction=f"Walk approximately {round(meters)} m from {stops[sid]['stop_name']} to {stops[board]['stop_name']}; straight-line guidance, no pedestrian route validation"))
                        newsteps.extend([dict(type='WAIT',minutes=round(depart-clock-walk,2),instruction=f"Wait at {stops[board]['stop_name']} (includes {buffer} min transfer buffer)"),dict(type='BOARD',instruction=f'Board {rid} · trip {trip}'),dict(type='RIDE',minutes=round(elapsed,2),instruction=f"Ride to {stops[target]['stop_name']}"),dict(type='ALIGHT',instruction=f"Alight at {stops[target]['stop_name']}")])
                        visit(target,finish,legs+[leg],newsteps,visited|set(seq[a:b+1]),used|{rid},walking+walk,delay+route_delay,max(crowd,load),events+route_events)
        for sid,walk,distance in origins:
            initial=[dict(type='WALK',minutes=round(walk,2),distance_meters=round(distance),instruction=f"Walk to {stops[sid]['stop_name']}; approximate straight-line guidance")]
            visit(sid,start+walk,[],initial,{sid},set(),walk,0,0,[])
        key={'faster':lambda o:o['total_minutes'],'less_crowd':lambda o:o['occupancy_ratio'],'less_delay':lambda o:o['delay_minutes'],'fewer_transfers':lambda o:o['transfers'],'most_reliable':lambda o:-o['reliability_score']}[body.preference]
        if getattr(body,'arrival_deadline',None):options=[o for o in options if datetime.fromisoformat(o['arrival_time'])<=body.arrival_deadline]
        if getattr(body,'max_wait_minutes',None) is not None:options=[o for o in options if o['wait_minutes']<=body.max_wait_minutes]
        secondary={'faster':lambda o:o['total_minutes'],'less_crowd':lambda o:o['occupancy_ratio'],'fewer_transfers':lambda o:o['transfers'],'most_reliable':lambda o:-o['reliability_score']}
        options.sort(key=lambda o:(key(o),*[secondary[p](o) for p in getattr(body,'secondary_preferences',[])],o['total_minutes'],o['option_id']))
        distinct={}
        for option in options:distinct.setdefault(option['option_id'],option)
        options=list(distinct.values())[:12]
        return dict(data_source='SYNTHETIC',prediction_mode=forecast['mode'],models={k:forecast[k] for k in ['eta_model','crowd_model','fallback_reason','history_source','horizons']},departure_time=departure.isoformat(),options=options,recommended_option_id=options[0]['option_id'] if options else None,message='Synthetic replay forecasts applied as planning assumptions over the full itinerary; not validated multi-hour forecasts.' if options else 'No feasible journey within the timetable, walking radius, transfer limit and active disruptions.',search_expansions=expanded,tracking_policy='Fresh GPS may replace scheduled boarding only within 15 minutes of server time. Future journeys use timetable waits.',walking_policy='Haversine distance at 1.4 m/s; straight-line guidance, not turn-by-turn directions.')
