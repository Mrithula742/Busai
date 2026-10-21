from ..utils.time_utils import utc_now


class NetworkEventService:
    def __init__(self, manager, gtfs):
        self.events = {}
        self.manager, self.gtfs = manager, gtfs

    def create(self, event):
        if event.event_id in self.events:
            raise ValueError('event_id already exists')
        if event.status != 'ACTIVE':
            raise ValueError('New events must be ACTIVE; use the clear endpoint to close them')
        if event.end_time is not None and event.end_time <= utc_now():
            raise ValueError('New event end_time must be in the future')
        if self.gtfs.loaded:
            if event.route_id and event.route_id not in self.gtfs.routes:
                raise ValueError('Unknown event route_id')
            if event.trip_id:
                trip = self.gtfs.trips.get(event.trip_id)
                if not trip or (event.route_id and event.route_id != trip['route_id']):
                    raise ValueError('Unknown trip_id or route/trip mismatch')
        self.events[event.event_id] = event
        self.manager.publish_message('NETWORK_EVENT_CREATED', event=event.model_dump(mode='json'))
        return event

    def clear(self, event_id):
        event = self.events[event_id]
        if event.status != 'CLEARED':
            # Keep the planned time window intact; clearing also cancels future events.
            event = event.model_copy(update={'status': 'CLEARED'})
            self.events[event_id] = event
            self.manager.publish_message('NETWORK_EVENT_CLEARED', event=event.model_dump(mode='json'))
        return event

    def expire(self):
        now = utc_now()
        for event in list(self.events.values()):
            if event.status == 'ACTIVE' and event.end_time is not None and event.end_time <= now:
                self.clear(event.event_id)

    def list(self, include_cleared=False):
        return [e for e in self.events.values() if include_cleared or e.status == 'ACTIVE']
