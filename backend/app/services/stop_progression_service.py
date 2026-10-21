from ..utils.geo import haversine_meters


class StopProgressionService:
    """Conservative stop-radius matching, not road map matching or ETA prediction."""

    def __init__(self, gtfs, radius=40, max_accuracy=100):
        self.gtfs, self.radius, self.max_accuracy = gtfs, radius, max_accuracy

    def associate(self, update, previous=None):
        sequence = self.gtfs.get_trip_stop_sequence(update.trip_id)
        if not self.gtfs.verify(update.route_id, update.trip_id) or not sequence:
            # Unverified hints must never look GTFS-associated.
            return update.model_copy(update={'current_stop_id': None, 'next_stop_id': None}), None
        ids = [s['stop_id'] for s in sequence]
        index = None
        if previous and previous.trip_id == update.trip_id and previous.route_id == update.route_id:
            index = previous.stop_sequence_index
        if update.source == 'SIMULATOR' and update.current_stop_id is not None:
            # Simulator supplies its exact sequence position; validate adjacent IDs.
            candidates = [i for i, sid in enumerate(ids) if sid == update.current_stop_id and (ids[i + 1] if i + 1 < len(ids) else None) == update.next_stop_id]
            if not candidates:
                raise ValueError('Simulator stop hints do not match the GTFS trip sequence')
            index = next((i for i in candidates if index is None or i >= index), candidates[0])
        elif update.accuracy_meters is None or update.accuracy_meters <= self.max_accuracy:
            def distance(i):
                stop = self.gtfs.get_stop(ids[i])
                return haversine_meters(update.latitude, update.longitude, stop['latitude'], stop['longitude'])
            if index is None:
                # Initial fix must actually be near a GTFS stop; don't invent progress.
                closest = min(range(len(ids)), key=distance)
                if distance(closest) <= self.radius:
                    index = closest
            elif index + 1 < len(ids) and distance(index + 1) <= self.radius:
                index += 1
        current = ids[index] if index is not None else None
        next_id = ids[index + 1] if index is not None and index + 1 < len(ids) else None
        return update.model_copy(update={'current_stop_id': current, 'next_stop_id': next_id}), index

    def approaching(self, buses, stop_id, limit=10):
        """Order observed upstream vehicles by stop-chain distance, never ETA."""
        result = []
        for bus in buses:
            index = bus.stop_sequence_index
            sequence = self.gtfs.get_trip_stop_sequence(bus.trip_id)
            if index is None or not bus.route_verified:
                continue
            target = next((i for i in range(index + 1, len(sequence)) if sequence[i]['stop_id'] == stop_id), None)
            if target is None:
                continue
            lat, lon = bus.latitude, bus.longitude
            remaining = 0
            for row in sequence[index + 1:target + 1]:
                stop = self.gtfs.get_stop(row['stop_id'])
                remaining += haversine_meters(lat, lon, stop['latitude'], stop['longitude'])
                lat, lon = stop['latitude'], stop['longitude']
            result.append({'bus': bus.model_dump(mode='json'), 'remaining_stop_chain_meters': round(remaining, 1)})
        return sorted(result, key=lambda item: item['remaining_stop_chain_meters'])[:limit]
