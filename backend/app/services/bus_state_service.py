from ..schemas.bus import BusState
from ..utils.time_utils import utc_now


class BusStateService:
    """Single-process store. Mutations run without awaits on one event loop."""

    def __init__(self, stale_seconds):
        self.buses = {}
        self.stale_seconds = stale_seconds

    def update(self, update, route_verified=False, data_source='unavailable', stop_index=None):
        now = utc_now()
        age = (now - update.timestamp).total_seconds()
        if age < -10:
            raise ValueError('GPS timestamp is more than 10 seconds in the future')
        previous = self.buses.get(update.bus_id)
        if previous and previous.source != update.source:
            raise ValueError('bus_id already belongs to a different GPS source')
        if previous and update.timestamp <= previous.timestamp:
            raise ValueError('GPS timestamp must be newer than the previous update')
        fields = update.model_dump(exclude={'accuracy'})
        if age >= self.stale_seconds:
            fields['status'] = 'STALE'
        bus = BusState(**fields, received_at=now, last_received_at=now, route_verified=route_verified, route_data_source=data_source, stop_sequence_index=stop_index)
        self.buses[bus.bus_id] = bus
        return bus

    def mark_stale(self):
        now = utc_now()
        changed = []
        for key, bus in list(self.buses.items()):
            if bus.status != 'STALE' and (now - bus.timestamp).total_seconds() >= self.stale_seconds:
                bus = bus.model_copy(update={'status': 'STALE'})
                self.buses[key] = bus
                changed.append(bus)
        return changed

    def list(self, include_stale=False, route_id=None):
        return [b for b in self.buses.values() if (include_stale or b.status != 'STALE') and (route_id is None or b.route_id == route_id)]
