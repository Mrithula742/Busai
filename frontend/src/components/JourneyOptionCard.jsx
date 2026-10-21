import { routeLabel } from '../services/journey.js';
import BusOptionCard from './BusOptionCard.jsx';
export default function JourneyOptionCard({ option, buses, stops, selected, onSelect, connected, onDetails, index = 0, reason }) {
  return <article className={`journey-card ${selected ? 'selected' : ''}`} data-testid="journey-option"><div className="row"><div><span className="eyebrow">OPTION {String.fromCharCode(65+index)} · DIRECT GTFS</span><h3>{routeLabel(option.route)}</h3></div><span className="route-pill">0 transfers</span></div>
    <p className="route-name">{option.route.route_long_name}</p>{reason&&<span className="route-reason">{reason}</span>}
    <div className="journey-stops"><div><span className="stop-dot"/><p><small>BOARD AT</small>{option.origin_stop.stop_name}</p></div><div><span className="stop-dot destination"/><p><small>GET OFF AT</small>{option.destination_stop.stop_name}</p></div></div>
    <p className="walking-summary">↗ {Math.round(option.origin_stop.distance_meters)} m · ~{option.origin_stop.estimated_walking_minutes.toFixed(1)} min walk</p>
    <button className="text-button" onClick={onSelect}>{selected ? 'Selected on map' : 'Show boarding & destination stops'}</button>{onDetails&&<button className="route-details-button" onClick={onDetails}>Open full route details <span>→</span></button>}
    <div className="bus-section"><h4>{buses.length} relevant {buses.length === 1 ? 'bus' : 'buses'}</h4>{!connected ? <p className="muted">Reconnecting — bus availability is unconfirmed.</p> : buses.length ? buses.map(bus => <BusOptionCard key={bus.bus_id} bus={bus} stops={stops}/>) : <p className="muted">No active bus with confirmed upstream trip progress. This route exists in GTFS, but service is not guaranteed now.</p>}</div>
    <div className="prediction-placeholders"><span>ETA <b>Model not connected</b></span><span>Crowd <b>Model not connected</b></span><span>Delay <b>Model not connected</b></span></div>
  </article>;
}
