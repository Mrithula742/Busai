import { useEffect, useRef, useState } from 'react';

export default function usePassengerLocation() {
  const [position, setPosition] = useState(null);
  const [permission, setPermission] = useState('not requested');
  const [error, setError] = useState('');
  const [locating, setLocating] = useState(false);
  const generation = useRef(0);
  useEffect(() => {
    let mounted = true, status;
    navigator.permissions?.query({ name: 'geolocation' }).then(result => {
      if (!mounted) return;
      status = result;
      const update = () => { setPermission(result.state); if (result.state === 'denied') { generation.current++; setPosition(null); setLocating(false); setError('Location permission denied. Enable it in your browser settings.'); } };
      update(); status.onchange = update;
    }).catch(() => {});
    return () => { mounted = false; generation.current++; if (status) status.onchange = null; };
  }, []);
  function locate() {
    if (locating) return;
    const session = ++generation.current;
    setError('');
    if (!window.isSecureContext || !navigator.geolocation) { setError('Location requires localhost or trusted HTTPS on your phone.'); return; }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(fix => {
      if (session !== generation.current) return;
      setLocating(false); setPermission('granted');
      const { latitude, longitude, accuracy } = fix.coords;
      if (![latitude, longitude, accuracy].every(Number.isFinite) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180 || accuracy < 0) { setError('The device returned an invalid location. Please retry.'); return; }
      setPosition({ latitude, longitude, accuracy, source: 'device', timestamp: fix.timestamp });
    }, failure => {
      if (session !== generation.current) return;
      setLocating(false);
      if (failure.code === 1) { setPermission('denied'); setPosition(null); }
      setError(failure.code === 1 ? 'Location permission denied. Enable it in your browser settings.' : 'Location unavailable. Move to an open area and try again.');
    }, { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 });
  }
  function useSample(stop) {
    generation.current++; setLocating(false); setError('');
    setPosition({ latitude: stop.latitude, longitude: stop.longitude, accuracy: null, source: 'sample', timestamp: Date.now() });
  }
  return { position, permission, error, locating, locate, useSample };
}
