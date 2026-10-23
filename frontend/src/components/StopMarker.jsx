import { useState } from 'react';
import L from 'leaflet';
import { Marker, Popup, Tooltip } from 'react-leaflet';
import { api } from '../services/api.js';

const stopIcon = selected => L.divIcon({
  className: `transit-stop-marker ${selected ? 'is-selected' : ''}`,
  html: '<span><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3" width="14" height="16" rx="3"/><path d="M5 12h14M8 19v3m8-3v3M8 7h8"/><circle cx="8.5" cy="15.5" r=".7"/><circle cx="15.5" cy="15.5" r=".7"/></svg></span>',
  iconSize: [32, 38], iconAnchor: [16, 38], tooltipAnchor: [0, -36], popupAnchor: [0, -36],
});
const icons = [stopIcon(false), stopIcon(true)];
const routeCache = new Map();
export default function StopMarker({ stop, selected, destination, onSelect }) {
  const [routes, setRoutes] = useState(routeCache.get(stop.stop_id));
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  async function loadRoutes() {
    if (routes || busy) return;
    setBusy(true); setError(false);
    try { const data = await api.stopRoutes(stop.stop_id); routeCache.set(stop.stop_id, data.routes); setRoutes(data.routes); }
    catch { setError(true); }
    finally { setBusy(false); }
  }
  const details = <div className="stop-marker-details"><small>BUS STOP</small><strong>{stop.stop_name}</strong>{destination && <span>Destination stop</span>}{Number.isFinite(stop.distance_meters) && <span>{Math.round(stop.distance_meters)} m away{Number.isFinite(stop.estimated_walking_minutes) && ` · ~${stop.estimated_walking_minutes.toFixed(1)} min walk`}</span>}<div className="stop-marker-routes">{routes ? [...new Set(routes.map(route=>route.route_short_name || route.route_id))].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true})).map(code=><b key={code}>{code}</b>) : <span>{error ? 'Route details unavailable' : 'Loading routes…'}</span>}{routes?.length===0 && <span>No routes listed</span>}</div></div>;
  return <Marker position={[stop.latitude, stop.longitude]} icon={icons[selected ? 1 : 0]} title={stop.stop_name} eventHandlers={{ mouseover: loadRoutes, click: () => { loadRoutes(); onSelect?.(stop); } }}><Tooltip direction="top" className="transit-stop-tooltip" opacity={1}>{details}</Tooltip><Popup>{details}<button className="text-button" onClick={()=>onSelect?.(stop)}>View stop details →</button></Popup></Marker>;
}
