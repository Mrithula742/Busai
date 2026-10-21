"""Use the backend's documented synthetic disruption policy for vehicle motion."""
from app.services.disruption_service import event_active, matches, impact
from app.utils.time_utils import utc_now

def active_events_for_bus(events,bus,now):
    a=bus.stops[bus.index]['stop_id'];b=bus.stops[min(bus.index+1,len(bus.stops)-1)]['stop_id']
    segment=f"{bus.config['route_id']}:{a}:{b}"
    return [e for e in events if event_active(e,now) and matches(e,bus.config['route_id'],bus.config['trip_id'],segment,[[s['latitude'],s['longitude']] for s in [bus.stops[bus.index],bus.stops[min(bus.index+1,len(bus.stops)-1)]]])]

def apply_network_events(bus,events,elapsed_seconds):
    bus.network_events=events
    effect=impact(events,bus.config['route_id'],utc_now(),bus.config['trip_id'],f"{bus.config['route_id']}:{bus.stops[bus.index]['stop_id']}:{bus.stops[min(bus.index+1,len(bus.stops)-1)]['stop_id']}",[[s['latitude'],s['longitude']] for s in [bus.stops[bus.index],bus.stops[min(bus.index+1,len(bus.stops)-1)]]])
    bus.delay_seconds=getattr(bus,'delay_seconds',0)+(elapsed_seconds if effect['blocked'] else max(0,elapsed_seconds-bus.dwell)*(1-1/effect['factor']))
    normal=bus.speed
    bus.display_speed=0 if effect['blocked'] else normal/effect['factor']
    if not effect['blocked']:
        bus.speed=bus.display_speed
        try:bus.advance(elapsed_seconds)
        finally:bus.speed=normal
