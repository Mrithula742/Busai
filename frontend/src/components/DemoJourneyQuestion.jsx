import { useState } from 'react';
import './demoJourney.css';
import DemoJourneyMap from './DemoJourneyMap.jsx';

export default function DemoJourneyQuestion() {
  const [origin, setOrigin] = useState('Madipakkam'), [destination, setDestination] = useState('Chennai Central');
  const [preference, setPreference] = useState('faster');
  const [selected, setSelected] = useState(null);
  const [reply, setReply] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  function change(setter, value) { setter(value); setReply(null); setError(''); }
  async function ask(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError(''); setReply(null);
    try {
      const response = await fetch('/api/demo/journey', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({question: `From ${origin.trim()} to ${destination.trim()}`, preference}) });
      if (!response.ok) throw new Error(`Demo request failed (${response.status}). Check that FastAPI is running and retry.`);
      const data = await response.json();
      setReply(data); setSelected(data.recommended_route_id || null);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="demo-planner" aria-label="Fictional Chennai journey demo">
    <span className="demo-badge">PRESENTATION MODE · SIMULATED DATA</span>
    <h2>Your journey. Your preference.</h2>
    <p>Compare demo bus routes around Chennai and Tamil Nadu.</p>
    <p className="demo-disclaimer">Fictional routes, crowd and delay values—not real MTC/TNSTC services, live information or model predictions. Do not use for travel.</p>
    <form onSubmit={ask}><fieldset disabled={busy} className="demo-fields">
      <label>Starting location<input required maxLength={100} value={origin} onChange={e=>change(setOrigin,e.target.value)}/></label>
      <label>Destination<input required maxLength={100} value={destination} onChange={e=>change(setDestination,e.target.value)}/></label>
      <label>I prefer<select value={preference} onChange={e=>change(setPreference,e.target.value)}><option value="faster">Faster journey</option><option value="less_crowd">Less crowd</option><option value="less_delay">Less delay</option></select></label>
      <button type="submit">{busy ? 'Comparing demo routes…' : 'Suggest my journey →'}</button>
    </fieldset></form>
    <div className="demo-examples">Try a scenario: {['Madipakkam → Chennai Central','Chennai → Kanchipuram'].map((s,i)=><button key={s} disabled={busy} onClick={()=>{setOrigin(i?'Chennai':'Madipakkam');setDestination(i?'Kanchipuram':'Chennai Central');setReply(null);setError('');}}>{s}</button>)}</div>
    {error && <p role="alert">{error}</p>}
    {reply && <div aria-live="polite"><p className="demo-answer">{reply.answer}</p>
      <div className="demo-route-grid">{reply.routes.map(r=><article className={`demo-route ${reply.recommended_route_id===r.route_id?'demo-recommended':''}`} key={r.route_id}>
        <span className="demo-badge">{reply.recommended_route_id===r.route_id?'RECOMMENDED FOR YOU':'ALTERNATIVE'} · DEMO</span>
        <h3>{r.route_id}</h3><p>{r.stops.join(' → ')}</p>
        <button type="button" aria-pressed={selected===r.route_id} onClick={()=>setSelected(r.route_id)}>{selected===r.route_id?'Selected on map':'Highlight on map'}</button>
        <div className="demo-total">{r.total_minutes}<small> min simulated total</small></div>
        <dl><div><dt>Crowd · simulated</dt><dd>{r.crowd_level}</dd></div><div><dt>Delay · simulated</dt><dd>{r.delay_minutes} min</dd></div><div><dt>Bus ride</dt><dd>{r.ride_minutes} min</dd></div><div><dt>Wait / walk</dt><dd>{r.wait_minutes} / {r.walking_minutes} min</dd></div></dl>
        <small>Total = walk + wait + ride + delay. Fixed scenario values; not calculated from GPS.</small>
      </article>)}</div>
      {reply.routes.length>0 && <DemoJourneyMap key={reply.routes.map(r=>r.route_id+ r.stops.join()).join()} routes={reply.routes} selected={selected} onSelect={setSelected}/>}
    </div>}
  </section>;
}
