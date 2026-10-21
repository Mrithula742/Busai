export function distanceMeters(a, b) {
  const radians = value => value * Math.PI / 180;
  const h = Math.sin(radians(b.latitude - a.latitude) / 2) ** 2 + Math.cos(radians(a.latitude)) * Math.cos(radians(b.latitude)) * Math.sin(radians(b.longitude - a.longitude) / 2) ** 2;
  return 6371000 * 2 * Math.atan2(Math.sqrt(Math.min(1, h)), Math.sqrt(Math.max(0, 1 - h)));
}

export function isStale(bus, now, seconds) {
  return bus.status === 'STALE' || !Number.isFinite(Date.parse(bus.timestamp)) || now - Date.parse(bus.timestamp) >= seconds * 1000;
}

export function relevantBuses(option, buses, now, staleSeconds, radius) {
  return Object.values(buses).filter(bus => {
    if (!bus.route_verified || bus.route_id !== option.route.route_id || isStale(bus, now, staleSeconds) || bus.stop_sequence_index === null || bus.stop_sequence_index === undefined) return false;
    return option.eligible_trip_segments.some(segment => segment.trip_id === bus.trip_id &&
      (bus.stop_sequence_index < segment.boarding_index ||
        (bus.stop_sequence_index === segment.boarding_index && distanceMeters(bus, option.origin_stop) <= radius)));
  }).sort((a, b) => a.bus_id.localeCompare(b.bus_id));
}

export function activeEvents(events, now) {
  return Object.values(events).filter(event => event.status === 'ACTIVE' && Date.parse(event.start_time) <= now && (!event.end_time || Date.parse(event.end_time) > now));
}

export function routeLabel(route) { return route?.route_short_name || route?.route_long_name || route?.route_id || 'Unverified route'; }
export function stopLabel(id, stops) { return id ? (stops[id]?.stop_name || id) : 'Not yet matched'; }
