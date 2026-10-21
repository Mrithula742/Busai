import { useEffect, useState } from 'react';
import { api } from '../services/api.js';

export default function DestinationSearch({ value, onSelect, disabled }) {
  const [query, setQuery] = useState(''), [results, setResults] = useState([]), [busy, setBusy] = useState(false), [error, setError] = useState(''), [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open || !query.trim()) { setResults([]); setBusy(false); return; }
    const controller = new AbortController();
    setBusy(true); setError('');
    const timer = setTimeout(() => {
      api.search(query.trim(), controller.signal).then(data => { setResults(data.stops); setBusy(false); }).catch(err => { if (err.name !== 'AbortError') { setError(err.message); setBusy(false); } });
    }, 220);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, open]);
  return <div className="destination-search">
    <label htmlFor="destination">Where are you going?</label>
    <div className="search-field"><span aria-hidden="true">↗</span><input id="destination" placeholder="Search a destination stop" value={query} disabled={disabled} autoComplete="off" aria-expanded={open} aria-controls="destination-results" onChange={e => { setQuery(e.target.value); setOpen(true); onSelect(null); }} onFocus={() => { if (!value) setOpen(true); }} onKeyDown={e => { if (e.key === 'Escape') setOpen(false); }} /></div>
    {open && query.trim() && <div id="destination-results" className="suggestions" aria-label="Destination suggestions">
      {busy ? <p>Searching GTFS stops…</p> : error ? <p role="alert">{error}</p> : results.length ? results.map(stop => <button type="button" key={stop.stop_id} onClick={() => { onSelect(stop); setQuery(stop.stop_name); setOpen(false); }}><span>{stop.stop_name}</span><small>{stop.stop_id}</small></button>) : <p>No matching destination in the loaded GTFS.</p>}
    </div>}
  </div>;
}
