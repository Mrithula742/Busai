import { CircleMarker, Popup, Tooltip } from 'react-leaflet';
export default function StopMarker({ stop, selected, destination, onSelect }) {
  return <CircleMarker center={[stop.latitude, stop.longitude]} radius={selected ? 8 : 5} pathOptions={{ color: selected ? '#b46425' : '#115c4d', weight: 2, fillColor: selected ? '#f3d596' : '#fff', fillOpacity: 1 }} eventHandlers={{click:()=>onSelect?.(stop)}}><Tooltip>{stop.stop_name}</Tooltip><Popup><strong>{stop.stop_name}</strong><p>{stop.stop_id}</p>{destination && <p>Destination stop</p>}{stop.distance_meters !== undefined && <p>{Math.round(stop.distance_meters)} m · ~{stop.estimated_walking_minutes.toFixed(1)} min walk</p>}</Popup></CircleMarker>;
}
