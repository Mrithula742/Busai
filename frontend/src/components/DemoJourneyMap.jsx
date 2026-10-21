import { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, useMap } from 'react-leaflet';
import { demoPoints, demoPosition } from '../services/demoMap.js';

function Fit({ routes }) {
  const map = useMap();
  useEffect(() => {
    const points = routes.flatMap(r => r.points);
    if (points.length) map.fitBounds(points, {padding: [40, 40], maxZoom: 14});
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map, routes]);
  return null;
}

export default function DemoJourneyMap({ routes, selected, onSelect }) {
  const mapped = useMemo(() => routes.map(r => ({...r, points: r.points || demoPoints(r)})).filter(r => r.points.length > 1), [routes]);
  const [tick, setTick] = useState(0), [paused, setPaused] = useState(false), [tileError, setTileError] = useState(false);
  useEffect(() => {
    if (paused) return;
    const timer = setInterval(() => setTick(t => t + 1), 500);
    return () => clearInterval(timer);
  }, [paused]);
  if (!mapped.length) return <p>No illustrative map coordinates for this demo.</p>;
  const first = mapped[0].points;
  return <section aria-label="Simulated route map">
    <h3>Compare routes on the map</h3>
    <p>Illustrative straight-line paths, not road directions. Animated dots are simulated buses—not GPS. Animation speed does not represent journey time; buses loop for presentation.</p>
    <button type="button" onClick={()=>setPaused(p=>!p)}>{paused?'Resume':'Pause'} simulated buses</button>
    <div className="demo-map" style={{height:380,marginTop:12}}>
      <MapContainer center={first[0]} zoom={11} style={{height:'100%',width:'100%'}}>
        <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' eventHandlers={{tileerror:()=>setTileError(true),load:()=>setTileError(false)}}/>
        <Fit routes={mapped}/>
        {mapped.map((r,i)=><Polyline key={r.route_id} positions={r.points} pathOptions={{color:r.route_id===selected?'#176b50':'#7958b5',weight:r.route_id===selected?7:4,opacity:r.route_id===selected?1:.6,dashArray:'9 6'}} eventHandlers={{click:()=>onSelect(r.route_id)}}><Tooltip>{r.route_id} · illustrative path</Tooltip></Polyline>)}
        <CircleMarker center={first[0]} radius={9} pathOptions={{color:'#164f98',fillOpacity:1}}><Tooltip permanent>Start: {mapped[0].stops[0]}</Tooltip></CircleMarker>
        <CircleMarker center={first[first.length-1]} radius={9} pathOptions={{color:'#ab4d16',fillOpacity:1}}><Tooltip permanent>Destination: {mapped[0].stops.at(-1)}</Tooltip></CircleMarker>
        {mapped.map((r,i)=><CircleMarker key={r.route_id} center={demoPosition(r.points,tick*(i?0.003:0.004)+i*0.25)} radius={8} pathOptions={{color:'#fff',weight:2,fillColor:r.route_id===selected?'#176b50':'#7958b5',fillOpacity:1}}><Tooltip permanent direction="bottom">SIM {r.route_id}</Tooltip></CircleMarker>)}
      </MapContainer>
    </div>
    {tileError && <p role="status">Background tiles unavailable. Demo route lines and buses still work.</p>}
    <p>Green: selected route · Purple: alternative · Blue: start · Orange: destination</p>
  </section>;
}
