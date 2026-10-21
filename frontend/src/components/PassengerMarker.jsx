import { Circle, CircleMarker, Popup } from 'react-leaflet';
export default function PassengerMarker({ position }) {
  if (!position) return null;
  const center = [position.latitude, position.longitude];
  return <>{position.accuracy > 0 && <Circle center={center} radius={position.accuracy} pathOptions={{ color: '#2868cf', weight: 1, fillOpacity: 0.07 }}/>}<CircleMarker center={center} radius={8} pathOptions={{ color: '#fff', weight: 3, fillColor: '#2868cf', fillOpacity: 1 }}><Popup><strong>{position.source === 'sample' ? 'SAMPLE origin — not device GPS' : 'Your location'}</strong><p>{position.latitude.toFixed(5)}, {position.longitude.toFixed(5)}</p>{position.accuracy !== null && <p>Accuracy ±{Math.round(position.accuracy)} m</p>}</Popup></CircleMarker></>;
}
