"""Computed journey comparison and isolated, reproducible scenario overlays."""
from copy import deepcopy
from datetime import timedelta
from .ai_journey_service import AIJourneyService


def compare(options, preference):
    if not options:
        return []
    fields={'faster':'total_minutes','less_crowd':'occupancy_ratio','most_reliable':'reliability_score'}
    result=[]
    fastest=min(o['total_minutes'] for o in options)
    for category,field in fields.items():
        winner=min(options,key=lambda o:((-o[field] if category=='most_reliable' else o[field]),o['total_minutes'],o['transfers'],o['option_id']))
        result.append(dict(category=category,option=winner,difference_from_fastest_minutes=round(winner['total_minutes']-fastest,1),factors=dict(total_minutes=winner['total_minutes'],wait_minutes=winner['wait_minutes'],transfers=winner['transfers'],occupancy_ratio=winner['occupancy_ratio'],reliability_score=winner['reliability_score'],penalties=winner['reliability_penalties']),explanation=f"Selected by {'highest' if category=='most_reliable' else 'lowest'} {field.replace('_',' ')} among {len(options)} returned feasible journeys; ties use duration and transfers."))
    return result


def enrich(result, preference):
    return dict(result,comparison=compare(result['options'],preference))


def what_if(gtfs,store,events,body,predictions):
    base=body.journey
    before=enrich(AIJourneyService(gtfs,store,events).search(base,predictions),base.preference)
    adjusted=deepcopy(predictions)
    keys=[key for key in adjusted['eta'] if key[0]==body.route_id]
    if not keys:raise ValueError('Unknown synthetic route')
    for key in keys:
        adjusted['eta'][key]=adjusted['eta'][key]*body.traffic_factor+body.delay_minutes/len(keys)
    adjusted['scenario_demand']={body.route_id:body.demand_factor}
    changes=(body.traffic_factor!=1 or body.delay_minutes>0 or body.demand_factor>1 or body.roadblock)
    projected=list(events)
    if changes:
        stop=gtfs.stops[keys[0][1]]
        # Identity OTHER event marks scenario risk without multiplying travel again.
        projected.append(dict(event_id='WHAT_IF_PREVIEW',event_type='ROAD_BLOCK' if body.roadblock else 'CROWD_SURGE',route_id=body.route_id,trip_id=None,segment_id=None,severity='LOW',start_time=base.departure_time,end_time=base.departure_time+timedelta(days=2),status='ACTIVE',latitude=stop['latitude'],longitude=stop['longitude']))
        # Crowd is handled by the route-specific demand factor, not fixed surge effects.
        projected[-1]['event_type']='ROAD_BLOCK' if body.roadblock else 'WHAT_IF'
    after=enrich(AIJourneyService(gtfs,store,projected).search(base,adjusted),base.preference)
    matched={o['option_id']:o for o in after['options']}
    deltas=[]
    for old in before['options']:
        new=matched.get(old['option_id'])
        deltas.append(dict(option_id=old['option_id'],route_id=old['route_id'],available=new is not None,total_minutes_delta=round(new['total_minutes']-old['total_minutes'],1) if new else None,ride_minutes_delta=round(new['ride_minutes']-old['ride_minutes'],1) if new else None,occupancy_delta=round(new['occupancy_ratio']-old['occupancy_ratio'],3) if new else None,reliability_delta=round(new['reliability_score']-old['reliability_score'],1) if new else None))
    return dict(mode='ISOLATED_WHAT_IF_SIMULATION',before=before,after=after,deltas=deltas,adjustments=body.model_dump(exclude={'journey'}),policy='Applies only to this preview. Travel × traffic factor + route delay distributed over all route segments; occupancy × route demand factor (clipped 0–1). No event or GPS state is changed. Reset discards the preview.')
