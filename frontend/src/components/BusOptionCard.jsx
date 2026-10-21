import { stopLabel } from '../services/journey.js';
export default function BusOptionCard({ bus, stops }) {
  return <div className="bus-option" data-testid={`bus-option-${bus.bus_id}`}><div className="row"><strong>{bus.bus_id}</strong><span className={`source-tag ${bus.source === 'SIMULATOR' ? 'sim' : ''}`}>{bus.source}</span></div><p>Current: {stopLabel(bus.current_stop_id, stops)}<br/>Next: {stopLabel(bus.next_stop_id, stops)}</p><small>Trip {bus.trip_id} · {bus.status}</small><small className="coordinates">{bus.latitude.toFixed(5)}, {bus.longitude.toFixed(5)}</small></div>;
}
