import { useEffect, useMemo, useRef, useState } from 'react';
import { divIcon } from 'leaflet';
import { Marker, Popup } from 'react-leaflet';
import { routeLabel, stopLabel } from '../services/journey.js';

export default function BusMarker({ bus, route, stops, stale }) {
  const marker = useRef(null);
  const [initialPosition] = useState(() => [bus.latitude, bus.longitude]);
  const previous = useRef(initialPosition);
  useEffect(() => {
    const target = [bus.latitude, bus.longitude];
    const instance = marker.current;
    if (!instance || (previous.current[0]===target[0]&&previous.current[1]===target[1])) return;
    const from = instance.getLatLng(), to = target, start = performance.now();
    const duration = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 700;
    let frame;
    const step = now => {
      const progress = duration ? Math.min(1,(now-start)/duration) : 1;
      const eased = progress<.5 ? 2*progress*progress : 1-((-2*progress+2)**2)/2;
      instance.setLatLng([from.lat+(to[0]-from.lat)*eased,from.lng+(to[1]-from.lng)*eased]);
      if(progress<1) frame=requestAnimationFrame(step);
    };
    frame=requestAnimationFrame(step); previous.current=target;
    return ()=>cancelAnimationFrame(frame);
  },[bus.latitude,bus.longitude]);
  const icon = useMemo(() => divIcon({ className: `bus-marker ${stale ? 'is-stale' : ''} ${bus.source === 'SIMULATOR' ? 'is-simulator' : 'is-phone'}`, html: '<span aria-hidden="true">▣</span>', iconSize: [30, 30], iconAnchor: [15, 15] }), [stale, bus.source]);
  return <Marker ref={marker} position={initialPosition} icon={icon} title={`${bus.bus_id} · ${stale ? 'STALE' : bus.status} · ${bus.source}`}>
    <Popup><div className="map-popup"><strong>{bus.bus_id} · {routeLabel(route || { route_id: bus.route_id })}</strong><p>Route ID: {bus.route_id}<br/>Trip: {bus.trip_id}</p><p>Current: {stopLabel(bus.current_stop_id, stops)}<br/>Next: {stopLabel(bus.next_stop_id, stops)}</p><p><b>{bus.source}</b><br/>Status: {stale ? 'STALE — last known position' : bus.status}<br/>Updated: {new Date(bus.timestamp).toLocaleTimeString()}</p>{bus.simulation_delay_seconds>0&&<p>Accumulated scenario delay: {(bus.simulation_delay_seconds/60).toFixed(1)} min</p>}{bus.source === 'SIMULATOR' && <small>Simulated GPS. Not an official operator feed.</small>}{!bus.route_verified && <p>Route/trip unverified</p>}</div></Popup>
  </Marker>;
}
