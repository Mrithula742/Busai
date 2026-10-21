import { useState } from 'react';
import { getJSON } from '../services/api.js';

export default function HistoricalModelDemo() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function run() {
    if (busy) return;
    setBusy(true); setError('');
    try { setData(await getJSON('/api/models/historical-demo')); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="journey-card" aria-label="Historical model demo">
    <h2>DCRNN historical model demo</h2>
    <p>Runs your saved model on recorded Salvador, Brazil data. This is separate from your origin/destination search—not a live Tamil Nadu ETA.</p>
    <button onClick={run} disabled={busy}>{busy ? 'Running model…' : 'Run historical model demo'}</button>
    {error && <p role="alert">{error}</p>}
    {data && <div aria-live="polite">
      <p><strong>HISTORICAL DEMO · {data.model}</strong><br/>{data.dataset}<br/>Recorded prediction time: {data.as_of}</p>
      <p>{data.warning}</p>
      <p>Saved reference test: {data.reference_verified ? 'passed' : 'not verified'}. Results are cached after the first run until backend restart.</p>
      <ul>{data.segments.map(s => <li key={`${s.route_id}-${s.from_stop_id}-${s.to_stop_id}`}>
        <strong>{s.from_stop_name} → {s.to_stop_name}</strong><br/>
        GTFS route ID {s.route_id} · predicted segment duration: {s.predicted_travel_time_seconds.toFixed(1)} seconds
        <br/>{s.observed_input_bins} observed input bins for this segment; missing history uses the model’s saved preprocessing.
      </li>)}</ul>
    </div>}
  </section>;
}
