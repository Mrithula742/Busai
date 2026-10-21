export async function getJSON(path, params, signal) {
  const query = new URLSearchParams(Object.entries(params || {}).filter(([, value]) => value !== undefined && value !== null && value !== ''));
  const response = await fetch(path + (query.size ? `?${query}` : ''), { signal });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`);
  }
  return response.json();
}

export const api = {
  health: () => getJSON('/api/health'),
  catalog: () => getJSON('/api/transit/catalog'),
  snapshot: () => getJSON('/api/snapshot'),
  search: (q, signal) => getJSON('/api/stops/search', { q, limit: 30 }, signal),
  nearby: (location, radius, signal) => getJSON('/api/stops/nearby', { latitude: location.latitude, longitude: location.longitude, radius, limit: 20 }, signal),
  journeys: (location, destination, radius, preference, signal) => getJSON('/api/journeys/options', { latitude: location.latitude, longitude: location.longitude, destination, radius, preference }, signal),
  tripStops: (tripId, signal) => getJSON(`/api/trips/${encodeURIComponent(tripId)}/stops`, {}, signal),
  routeInfo: (routeId, signal) => getJSON(`/api/routes/${encodeURIComponent(routeId)}`, {}, signal),
  routeTimetable: (routeId, stopId, signal) => getJSON(`/api/routes/${encodeURIComponent(routeId)}/timetable`, { stop_id: stopId }, signal),
  stopRoutes: (stopId, signal) => getJSON(`/api/stops/${encodeURIComponent(stopId)}/routes`, {}, signal),
};
