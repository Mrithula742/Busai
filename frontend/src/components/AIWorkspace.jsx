import { busLabel } from '../services/busLabels.js';
import { useEffect, useRef, useState } from 'react';
import MapView from './MapView.jsx';
import { aiRequest, plannerPayload } from '../services/ai.js';
import { activeEvents } from '../services/journey.js';
import './aiWorkspace.css';
import {SmartComparison,JourneyAssistant,SimulationStudio,BoardingAlertCenter,PerformanceDashboard} from './ShowcasePanels.jsx';

function localDate(){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}
function clock(value){return new Date(value).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit'});}

export default function AIWorkspace({page,live,connected,gps,now,staleSeconds,onNavigate}) {
  const [catalog,setCatalog]=useState(null),[insights,setInsights]=useState(null),[reply,setReply]=useState(null),[selected,setSelected]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[refreshing,setRefreshing]=useState(false),[updated,setUpdated]=useState(null);
  const [form,setForm]=useState({origin:'MAD',destination:'CEN',date:localDate(),time:'08:00',preference:'less_crowd',maxTransfers:2,buffer:5,useLocation:false});
  const [scenario,setScenario]=useState({route_id:'SYN_A',event_type:'CONGESTION',severity:'HIGH'}),[scenarioBusy,setScenarioBusy]=useState(false),[scenarioError,setScenarioError]=useState('');
  const [selectionNotice,setSelectionNotice]=useState('');
  const selectedRef=useRef(null);
  const alertMemory=useRef({seen:new Set(),arrivals:new Map()});
  const [twin,setTwin]=useState(null),[twinError,setTwinError]=useState(''),[twinBusy,setTwinBusy]=useState(false),[focusedId,setFocusedId]=useState(null);
  const lastPayload=useRef(null),requestId=useRef(0),mounted=useRef(true);
  useEffect(()=>{mounted.current=true;const c=new AbortController();Promise.all([aiRequest('/api/synthetic/catalog',null,c.signal),aiRequest('/api/models/insights',null,c.signal)]).then(([catalog,models])=>{setCatalog(catalog);setInsights(models);}).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>{mounted.current=false;c.abort();};},[]);
  async function run(payload,refresh=false){
    const id=++requestId.current;
    if(refresh)setRefreshing(true);else {setBusy(true);setReply(null);}
    setError('');
    try{const data=await aiRequest('/api/ai/journeys',payload);if(!mounted.current||id!==requestId.current)return;setReply(data);setUpdated(new Date().toISOString());lastPayload.current=payload;const previous=selectedRef.current;const next=refresh&&data.options.some(o=>o.option_id===previous)?previous:data.recommended_option_id;setSelectionNotice(refresh&&previous&&next!==previous?'Your previous journey is no longer feasible. Review the newly selected alternative.':'');setSelected(next);selectedRef.current=next;}
    catch(e){if(mounted.current&&id===requestId.current)setError(e.message);}
    finally{if(mounted.current&&id===requestId.current){setBusy(false);setRefreshing(false);}}
  }
  useEffect(()=>{const timer=setInterval(()=>{if(lastPayload.current&&!document.hidden)run(lastPayload.current,true);},10000);return()=>clearInterval(timer);},[]);
  function change(key,value){requestId.current++;lastPayload.current=null;setReply(null);setSelected(null);selectedRef.current=null;setSelectionNotice('');setBusy(false);setRefreshing(false);setError('');setForm(f=>({...f,[key]:value}));}
  async function submit(e){e.preventDefault();if(form.useLocation&&gps.position?.source!=='device'){setError('Use the location button and allow browser location access first.');return;}await run(plannerPayload(form,gps.position));}
  async function activate(){setScenarioBusy(true);setScenarioError('');try{await aiRequest('/api/simulation/scenarios',scenario);if(lastPayload.current)await run(lastPayload.current,true);}catch(e){setScenarioError(e.message);}finally{setScenarioBusy(false);}}
  async function clear(event){setScenarioBusy(true);setScenarioError('');try{await aiRequest(`/api/network-events/${encodeURIComponent(event.event_id)}/clear`,{});if(lastPayload.current)await run(lastPayload.current,true);}catch(e){setScenarioError(e.message);}finally{setScenarioBusy(false);}}
  const choice=reply?.options.find(o=>o.option_id===selected),stops=Object.fromEntries((catalog?.stops||[]).map(s=>[s.stop_id,{...s,latitude:Number(s.stop_lat),longitude:Number(s.stop_lon)}]));
  const routeIds=(catalog?.routes||[]).map(r=>r.route_id),routes=Object.fromEntries(routeIds.map(r=>[r,{route_id:r,route_short_name:busLabel(r)}]));
  const events=activeEvents(live.events,now),visible=page==='AI Journey'||page==='My Journey'||page==='Model Insights';
  const path=choice?.legs.flatMap(l=>l.stop_ids.map(s=>stops[s]))||[];
  const boardingStop=choice?.legs[0]?.stop_ids[0];
  useEffect(()=>{const c=new AbortController();let active=true,inflight=false;
    async function sync(){if(inflight)return;inflight=true;setTwinBusy(true);try{const data=await aiRequest('/api/twin'+(boardingStop?'?boarding_stop='+encodeURIComponent(boardingStop):''),null,c.signal);if(active){setTwin(data);setTwinError('');}}catch(e){if(active&&e.name!=='AbortError')setTwinError(e.message);}finally{inflight=false;if(active)setTwinBusy(false);}}
    if(['AI Journey','My Journey'].includes(page))sync();
    const timer=setInterval(()=>{if(['AI Journey','My Journey'].includes(page)&&!document.hidden)sync();},5000);
    return()=>{active=false;c.abort();clearInterval(timer);};
  },[page,boardingStop]);
  function choose(id){setSelected(id);selectedRef.current=id;setSelectionNotice('');setFocusedId(null);}
  function applyIntent(parameters){const local=parameters.departure_time;setForm(f=>({...f,origin:parameters.origin,destination:parameters.destination,date:local.slice(0,10),time:local.slice(11,16),preference:parameters.preference,maxTransfers:parameters.max_transfers,useLocation:false}));run(parameters);}
  if(!visible&&page!=='Simulation Studio')return null;
  return <section className="ai-workspace" aria-label="Integrated AI journey system">
    <div className="ai-heading"><div><span className="eyebrow">YOUR JOURNEY · YOUR PRIORITIES</span><h1>{page==='Model Insights'?'Model insights':page==='My Journey'?'Your selected journey':page==='Simulation Studio'?'Explore the what-ifs.':'Make the connection.'}</h1><p>Compare buses, walking time and crowd levels to find your best journey.</p></div></div>
    {page==='AI Journey'&&catalog&&<JourneyAssistant catalog={catalog} departureTime={`${form.date}T${form.time}:00+05:30`} onApply={applyIntent}/>}
    {page==='AI Journey'&&catalog&&<form onSubmit={submit} className="ai-form"><fieldset disabled={busy}>
      <label>Starting stop<select aria-label="AI starting stop" value={form.origin} disabled={form.useLocation} onChange={e=>change('origin',e.target.value)}>{catalog.stops.map(s=><option key={s.stop_id} value={s.stop_id}>{s.stop_name}</option>)}</select></label>
      <label>Destination<select aria-label="AI destination" value={form.destination} onChange={e=>change('destination',e.target.value)}>{catalog.stops.map(s=><option key={s.stop_id} value={s.stop_id}>{s.stop_name}</option>)}</select></label>
      <label>Departure date (IST)<input required type="date" value={form.date} onChange={e=>change('date',e.target.value)}/></label>
      <label>Departure time (IST)<input required type="time" min="06:00" max="21:59" value={form.time} onChange={e=>change('time',e.target.value)}/></label>
      <label>Journey preference<select aria-label="AI preference" value={form.preference} onChange={e=>change('preference',e.target.value)}><option value="faster">Fastest journey</option><option value="less_crowd">Lowest crowd</option><option value="fewer_transfers">Fewer transfers</option><option value="most_reliable">Most reliable</option></select></label>
      <label>Maximum transfers<select value={form.maxTransfers} onChange={e=>change('maxTransfers',e.target.value)}><option value="0">Direct only</option><option value="1">One transfer</option><option value="2">Two transfers</option></select></label>
      <label>Transfer buffer (minutes)<input type="number" min="2" max="30" value={form.buffer} onChange={e=>change('buffer',e.target.value)}/></label>
      <label className="ai-location"><input type="checkbox" checked={form.useLocation} onChange={e=>change('useLocation',e.target.checked)}/> Start from device location</label>
      {form.useLocation&&<button type="button" onClick={gps.locate}>Allow device location</button>}
      <button className="primary-cta" type="submit">{busy?'Finding feasible journeys…':'Find AI journeys'}</button>
    </fieldset></form>}
    {selectionNotice&&<p role="status" className="ai-notice">{selectionNotice}</p>}{error&&<p role="alert" className="error-message">{error}</p>}
    {page==='Model Insights'&&<PerformanceDashboard/>}
    {(page==='AI Journey'||page==='Simulation Studio')&&<SimulationStudio payload={reply?lastPayload.current:null} routeIds={routeIds}/>}
    <div hidden={!['AI Journey','My Journey'].includes(page)}><BoardingAlertCenter journey={choice} twin={twin} now={now} connected={connected} updated={updated} alertMemory={alertMemory} sessionKey={lastPayload.current?.departure_time}/></div>
    {reply&&['AI Journey','My Journey'].includes(page)&&<><div className="ai-result-heading"><h2>{reply.options.length} feasible journey options</h2><small>{refreshing?'Refreshing estimates…':updated?`Updated ${new Date(updated).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',second:'2-digit'})} · refreshes every 10 seconds`:''}</small><button disabled={busy||refreshing} onClick={()=>run(lastPayload.current,true)}>Refresh estimates</button></div>
      <details className="ai-model-label"><summary>How estimates are calculated</summary><p>{reply.message}</p><p>ETA: {reply.models.eta_model} · Crowd: {reply.models.crowd_model} · {reply.prediction_mode}</p></details>{reply.models.fallback_reason&&<p role="status">Fallback reason: {reply.models.fallback_reason}</p>}
      {page==='AI Journey'&&<SmartComparison reply={reply} selected={selected} onSelect={choose}/>}
      {page==='AI Journey'&&<div className="ai-results">{reply.options.map((o,i)=><article data-testid="ai-option" className={`ai-option ${selected===o.option_id?'is-selected':''}`} key={o.option_id}><span className="eyebrow">{i===0?'RECOMMENDED FOR YOUR PREFERENCE':'ALTERNATIVE'} · {o.transfers} TRANSFERS</span><h3>{busLabel(o.route_id)}</h3><div className="ai-time">{o.total_minutes}<small> min · arrive {clock(o.arrival_time)}</small></div><dl><div><dt>Walking</dt><dd>{o.walking_minutes} min</dd></div><div><dt>Waiting</dt><dd>{o.wait_minutes} min</dd></div><div><dt>Ride</dt><dd>{o.ride_minutes} min</dd></div><div><dt>Crowd</dt><dd>{o.crowd_level} · {Math.round(o.occupancy_ratio*100)}%</dd></div><div><dt>Reliability index</dt><dd>{o.reliability_score}/100</dd></div><div><dt>Delay risk</dt><dd>{o.delay_risk}</dd></div><div><dt>Transfer risk</dt><dd>{o.transfer_risk}</dd></div></dl><p className="ai-explanation">{o.explanations[0]}</p><button aria-pressed={selected===o.option_id} onClick={()=>choose(o.option_id)}>Select this journey</button></article>)}</div>}
      {choice&&<section className="ai-selected" data-testid="ai-selected"><div className="ai-result-heading"><h2>{busLabel(choice.route_id)}</h2>{page==='AI Journey'&&<button onClick={()=>onNavigate('My Journey')}>Track in My Journey</button>}</div><p>Expected arrival {clock(choice.arrival_time)} IST · upcoming boarding: {choice.legs[0].boarding_stop}</p><ol className="ai-timeline">{choice.itinerary.map((step,i)=><li key={i}><b>{step.type.replaceAll('_',' ')}</b><span>{busLabel(step.instruction)}{step.minutes!==undefined?` · ${step.minutes} min`:''}</span></li>)}</ol><h3>Why this journey?</h3><ul>{choice.explanations.map(reason=><li key={busLabel(reason)}>{busLabel(reason)}</li>)}</ul><p>Scenario duration range: {choice.duration_range_minutes.join('–')} min. {choice.range_assumption}</p><p>{reply.tracking_policy}</p><div className="ai-tracking-status">{choice.legs.map((leg,i)=><p key={i}>{busLabel(leg.route_id)}: {leg.bus?`${leg.bus.bus_id} · ${leg.bus.source} · GPS updated ${clock(leg.bus.timestamp)}`:'Scheduled boarding estimate; no fresh qualifying GPS bus associated'}</p>)}</div></section>}
      <MapView position={form.useLocation?gps.position:null} stops={Object.values(stops)} buses={live.buses} events={events} routes={routes} allStops={stops} selected={null} destination={null} now={now} staleSeconds={staleSeconds} fallback={Object.values(stops)[0]} connected={connected} focusedVehicle={live.buses[focusedId]} routeSequence={path} routeGeometry={choice?.legs.flatMap(l=>l.geometry)||[]} onStopSelect={()=>{}}/>
    </>}
    {page==='My Journey'&&!reply&&<p>Choose a journey in AI Journey to keep its itinerary and refreshed estimates here.</p>}
    {page==='AI Journey'&&<details className="ai-scenarios"><summary>Journey conditions</summary><p>Scenarios apply during their active real-clock window. Choose a departure near now to observe their effects. Roadblocks and breakdowns make affected segments unavailable.</p><div className="ai-scenario-fields"><label>Affected route<select value={scenario.route_id} onChange={e=>setScenario(s=>({...s,route_id:e.target.value}))}>{routeIds.map(r=><option key={r} value={r}>{busLabel(r)}</option>)}</select></label><label>Scenario<select value={scenario.event_type} onChange={e=>setScenario(s=>({...s,event_type:e.target.value}))}>{['CONGESTION','ROAD_BLOCK','BREAKDOWN','TEMPORARY_DELAY','HEAVY_RAIN','CROWD_SURGE'].map(t=><option key={t}>{t}</option>)}</select></label><button disabled={scenarioBusy} onClick={activate}>Apply conditions</button></div>{scenarioError&&<p role="alert">{scenarioError}</p>}{events.filter(e=>e.event_id.startsWith('SYN_SCENARIO_')).map(e=><p key={e.event_id}>{busLabel(e.route_id)} · {e.event_type} <button disabled={scenarioBusy} onClick={()=>clear(e)}>Clear scenario</button></p>)}</details>}
    {(page==='Model Insights'||page==='AI Journey')&&insights&&<details open={page==='Model Insights'} className="ai-insights"><summary>Model insights · {insights.status}</summary>{insights.fallback_reason&&<p>{insights.fallback_reason}</p>}<div className="ai-results">{Object.entries(insights.models).map(([kind,m])=><article className="ai-option" key={kind}><span className="eyebrow">SYNTHETIC-TRAINED · {kind.toUpperCase()}</span><h3>{m.architecture}</h3><p>{m.history_steps} historical steps · {m.bin_minutes}-minute bins · one-step horizon</p><p>Held-out MAE: {m.test_mae.toFixed(4)} {m.units}</p><p>Persistence MAE: {m.persistence_test_mae.toFixed(4)} {m.units}</p><p>{m.train_windows} training / {m.validation_windows} validation / {m.test_windows} test windows</p></article>)}</div><h3>Original research experiments</h3>{Object.entries(insights.original_experiments).map(([name,m])=><p key={name}><b>{name.toUpperCase()}</b>: {m.usage}</p>)}<ul>{insights.limitations.map(v=><li key={v}>{v}</li>)}</ul></details>}
  </section>;
}
