import { divIcon } from 'leaflet';
import { Marker, Popup } from 'react-leaflet';
const icon = divIcon({ className: 'event-marker', html: '<span aria-hidden="true">!</span>', iconSize: [28, 28], iconAnchor: [14, 14] });
export default function NetworkEventMarker({ event }) {
  return <Marker position={[event.latitude, event.longitude]} icon={icon} title={`${event.event_type}: ${event.description}`}><Popup><strong>{event.event_type.replaceAll('_', ' ')}</strong><p>{event.description}</p>{event.severity && <p>Severity: {event.severity}</p>}{event.route_id && <p>Affected route: {event.route_id}</p>}<small>Scenario effects apply in the integrated AI planner during the active time window</small></Popup></Marker>;
}
