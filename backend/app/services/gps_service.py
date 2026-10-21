class GPSService:
    def __init__(self, store, gtfs, manager, progression):
        self.store, self.gtfs, self.manager = store, gtfs, manager
        self.progression = progression
        self.last_inputs = {}

    def ingest(self, update):
        original = update.model_dump(exclude={'accuracy'})
        if self.last_inputs.get(update.bus_id) == original:
            # Lost HTTP response: acknowledge an exact retry without refreshing GPS age.
            self.refresh_stale()
            return self.store.buses[update.bus_id]
        verified = self.gtfs.verify(update.route_id, update.trip_id)
        previous = self.store.buses.get(update.bus_id)
        update, index = self.progression.associate(update, previous)
        bus = self.store.update(update, verified, self.gtfs.data_source, index)
        self.last_inputs[update.bus_id] = original
        self.manager.publish(bus)
        if previous is not None and previous.status != bus.status:
            self.manager.publish(bus, 'BUS_STATUS_CHANGED')
        return bus

    def refresh_stale(self):
        for bus in self.store.mark_stale():
            self.manager.publish(bus, 'BUS_STATUS_CHANGED')
