"""Shared deterministic simulation policy. These are assumptions, not learned effects."""
from datetime import datetime
import math
SEVERITY={'LOW':1.1,'MODERATE':1.3,'HIGH':1.6,'CRITICAL':2.0}
STOP_EVENTS={'ROAD_BLOCK','BREAKDOWN'}

def event_active(event,now,until=None):
    def date(value):return datetime.fromisoformat(value.replace('Z','+00:00')) if isinstance(value,str) else value
    return event['status']=='ACTIVE' and (date(event['start_time'])<until if until is not None else date(event['start_time'])<=now) and (not event.get('end_time') or now<date(event['end_time']))

def nearby(event,points):
    if not points:return False
    # Local equirectangular projection for a 500 m scenario influence corridor.
    lat,lon=event['latitude'],event['longitude'];scale=111195
    coords=[((p[1]-lon)*math.cos(math.radians(lat))*scale,(p[0]-lat)*scale) for p in points]
    for a,b in zip(coords,coords[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1];denom=dx*dx+dy*dy
        t=max(0,min(1,-(a[0]*dx+a[1]*dy)/denom)) if denom else 0
        if math.hypot(a[0]+t*dx,a[1]+t*dy)<=500:return True
    return False

def matches(event,route,trip=None,segment=None,points=None):
    return (bool(event.get('route_id') or event.get('trip_id') or event.get('segment_id')) or nearby(event,points)) and (not event.get('route_id') or event['route_id']==route) and (not event.get('trip_id') or event['trip_id']==trip) and (not event.get('segment_id') or event['segment_id']==segment)

def impact(events,route,now,trip=None,segment=None,points=None,until=None):
    active=[e for e in events if event_active(e,now,until) and matches(e,route,trip,segment,points)]
    blocked=any(e['event_type'] in STOP_EVENTS for e in active)
    factor=max([SEVERITY.get(e.get('severity'),1.3) for e in active if e['event_type'] not in ('CROWD_SURGE','WHAT_IF')] or [1.0])
    crowd=min(.4,sum(.2 for e in active if e['event_type']=='CROWD_SURGE'))
    return dict(blocked=blocked,factor=factor,crowd_add=crowd,events=[e['event_id'] for e in active])
