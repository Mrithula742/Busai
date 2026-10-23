import L from 'leaflet';
import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, useMap, useMapEvents, ZoomControl, Marker, Pane, Polyline, CircleMarker, Tooltip } from 'react-leaflet';
import PassengerMarker from './PassengerMarker.jsx';
import BusMarker from './BusMarker.jsx';
import StopMarker from './StopMarker.jsx';
import NetworkEventMarker from './NetworkEventMarker.jsx';
import { isStale } from '../services/journey.js';

function Camera({ position, selected, destination, fallback, routeSequence, routeSequences, routeGeometry, focusedVehicle }) {
  const map = useMap();
  useEffect(() => {
    const allPoints = routeSequence?.length>1 ? (routeGeometry?.length>1?routeGeometry:routeSequence.map(stop=>[stop.latitude,stop.longitude])) : routeSequences?.flatMap(route=>route.geometry?.length>1?route.geometry:(route.stops||[]).map(stop=>[stop.latitude,stop.longitude]));
    if(focusedVehicle) map.setView([focusedVehicle.latitude,focusedVehicle.longitude],16);
    else if (allPoints?.length > 1) map.fitBounds(allPoints, { padding: [65, 65], maxZoom: 16 });
    else if (selected && destination) map.fitBounds([[selected.latitude, selected.longitude], [destination.latitude, destination.longitude]], { padding: [70, 70], maxZoom: 16 });
    else if (selected) map.setView([selected.latitude, selected.longitude], 15);
    else if (position) map.setView([position.latitude, position.longitude], 15);
    else if (fallback) map.setView([fallback.latitude, fallback.longitude], 13);
  }, [map, position, selected, destination, fallback, routeSequence, routeSequences, routeGeometry, focusedVehicle]);
  useEffect(() => { const observer = new ResizeObserver(() => map.invalidateSize()); observer.observe(map.getContainer()); return () => observer.disconnect(); }, [map]);
  return null;
}

function StopLayer({ allStops, nearby, selected, destination, onSelect }) {
  const map = useMapEvents({ moveend: () => setRevision(value=>value+1), zoomend: () => setRevision(value=>value+1) });
  const [,setRevision] = useState(0);
  const candidates = new Map(Object.values(allStops || {}).map(stop=>[stop.stop_id,stop]));
  nearby.forEach(stop=>candidates.set(stop.stop_id,stop));
  const pinned = [selected,destination].filter(Boolean);
  pinned.forEach(stop=>candidates.delete(stop.stop_id));
  const groups = new Map();
  const zoom=map.getZoom();
  const cellSize=zoom<14?110:zoom<15?86:zoom<17?48:30;
  const bounds=map.getBounds();
  candidates.forEach(stop=>{
    if(!bounds.contains([stop.latitude,stop.longitude]))return;
    const pixel=map.project([stop.latitude,stop.longitude],zoom);
    const key=`${Math.floor(pixel.x/cellSize)}:${Math.floor(pixel.y/cellSize)}`;
    if(!groups.has(key))groups.set(key,[]);
    groups.get(key).push(stop);
  });
  return <>{[...groups.entries()].map(([key,group])=>{
    if(group.length===1)return <StopMarker key={group[0].stop_id} stop={group[0]} onSelect={onSelect}/>;
    const center=[group.reduce((sum,s)=>sum+s.latitude,0)/group.length,group.reduce((sum,s)=>sum+s.longitude,0)/group.length];
    const icon=L.divIcon({className:'stop-cluster-marker',html:`<span>${group.length}</span>`,iconSize:[38,38],iconAnchor:[19,19]});
    return <Marker key={key} position={center} icon={icon} title={`${group.length} bus stops — click to zoom`} eventHandlers={{click:()=>map.fitBounds(group.map(stop=>[stop.latitude,stop.longitude]),{padding:[55,55],maxZoom:Math.min(zoom+2,19)})}}><Tooltip direction="top">{group.length} bus stops · click to explore</Tooltip></Marker>;
  })}{[...new Map(pinned.map(stop=>[stop.stop_id,stop])).values()].map(stop=><StopMarker key={stop.stop_id} stop={stop} selected destination={destination?.stop_id===stop.stop_id} onSelect={onSelect}/>)}</>;

}

export default function MapView({ position, stops, buses, events, routes, allStops, selected, destination, now, staleSeconds, fallback, connected, routeSequence = [], routeSequences = [], routeGeometry = [], onStopSelect, selectedOption, focusedVehicle }) {
  const [tileError, setTileError] = useState(false);
  return <div className="map-wrap" aria-label="Live bus map"><MapContainer center={[20, 78]} zoom={5} zoomControl={false}>
    <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" eventHandlers={{ tileerror: () => setTileError(true), load: () => setTileError(false) }}/>
    <ZoomControl position="bottomright"/><Camera position={position} selected={selected} destination={destination} fallback={fallback} routeSequence={routeSequence} routeSequences={routeSequences} routeGeometry={routeGeometry} focusedVehicle={focusedVehicle}/>
    {routeSequences.map(({id,stops:sequence,color,geometry},routeIndex)=>{const active=id===selectedOption;const paint=active?'#176b5b':selectedOption?'#b6c1bc':color;const line=geometry?.length>1?geometry:sequence.map(stop=>[stop.latitude,stop.longitude]);return <React.Fragment key={id}><Polyline positions={line} pathOptions={{color:paint,weight:active?7:routeIndex===0?5:4,opacity:active ? 0.96 : selectedOption ? 0.48 : 0.86,dashArray:geometry?.length>1?undefined:'5 7'}}/>{sequence.map((stop,index)=><CircleMarker key={`${id}-${stop.stop_id}-${index}`} center={[stop.latitude,stop.longitude]} radius={index===0||index===sequence.length-1?7:4} pathOptions={{color:'#fff',weight:2,fillColor:index===0?paint:index===sequence.length-1?'#bd9250':paint,fillOpacity:1}}><Tooltip>{stop.stop_name}</Tooltip></CircleMarker>)}</React.Fragment>})}
    {routeSequence.length>1&&<><Polyline positions={routeGeometry?.length>1?routeGeometry:routeSequence.map(stop=>[stop.latitude,stop.longitude])} pathOptions={{color:'#176b5b',weight:6,opacity:.82,dashArray:routeGeometry?.length>1?undefined:'5 7'}}/>{routeSequence.map((stop,index)=><CircleMarker key={`${stop.stop_id}-${index}`} center={[stop.latitude,stop.longitude]} radius={index===0||index===routeSequence.length-1?7:4} pathOptions={{color:'#fff',weight:2,fillColor:index===0?'#176b5b':index===routeSequence.length-1?'#bd9250':'#6c8c7b',fillOpacity:1}}><Tooltip>{stop.stop_name}</Tooltip></CircleMarker>)}</>}
    <Pane name="passenger" style={{ zIndex: 650 }}><PassengerMarker position={position}/></Pane>
    <StopLayer allStops={allStops} nearby={stops} selected={selected} destination={destination} onSelect={onStopSelect}/>
    {Object.values(buses).map(bus => <BusMarker key={bus.bus_id} bus={bus} stops={allStops} route={routes[bus.route_id]} stale={isStale(bus, now, staleSeconds)}/>)}
    {events.map(event => <NetworkEventMarker key={event.event_id} event={event}/>)}
  </MapContainer><div className="map-top-label"><span className={`live-dot ${!connected ? 'offline' : ''}`}/>{connected ? 'Live GPS map' : 'Connection interrupted — last known positions'}</div>
    {tileError && <div className="tile-warning">Map tiles unavailable. GPS markers still update.</div>}
    <div className="map-legend"><span><i className="legend-passenger"/>You</span>{routeSequences.length>0&&routeSequences.map((route,index)=><span key={route.id}><i style={{background:selectedOption===route.id?'#176b5b':selectedOption?'#b6c1bc':route.color}}/>{index===0?'Route A':'Route B'}</span>)}{routeSequence.length>0&&<span><i style={{background:'#176b5b'}}/>Selected route</span>}<span><i className="legend-stop"/>Stop</span><span><i className="legend-bus"/>Bus</span><span><i className="legend-stale"/>Stale</span><span><i className="legend-event"/>Event</span></div>
  </div>;
}
