import DevBeezLogo from '../components/DevBeezLogo.jsx';
import { useEffect, useMemo, useState } from 'react';
import { api } from '../services/api.js';
import { connectLive, emptyState } from '../services/websocket.js';
import { activeEvents, isStale } from '../services/journey.js';
import usePassengerLocation from '../hooks/usePassengerLocation.js';
import DestinationSearch from '../components/DestinationSearch.jsx';
import NearbyStops from '../components/NearbyStops.jsx';
import MapView from '../components/MapView.jsx';
import RoutesDirectory from '../components/RoutesDirectory.jsx';
import MyJourneyPanel from '../components/MyJourneyPanel.jsx';
import RouteStopTimeline from '../components/RouteStopTimeline.jsx';
import { parseJourneyIntent } from '../services/journeyIntent.js';
import { walkingRankedDistinctRoutes } from '../services/recommendations.js';
import HistoricalModelDemo from '../components/HistoricalModelDemo.jsx';
import DemoJourneyQuestion from '../components/DemoJourneyQuestion.jsx';
import SyntheticJourney from '../components/SyntheticJourney.jsx';
import AIWorkspace from '../components/AIWorkspace.jsx';

const CHENNAI_CENTER = Object.freeze({latitude:13.0604,longitude:80.2496});
const EMPTY_ARRAY = Object.freeze([]);

export default function Home() {
  const gps = usePassengerLocation();
  const [live, setLive] = useState(emptyState), [connection, setConnection] = useState('connecting');
  const [catalog, setCatalog] = useState(null), [health, setHealth] = useState(null), [catalogError, setCatalogError] = useState('');
  const [destination, setDestination] = useState(null), [preference, setPreference] = useState(''), [radius, setRadius] = useState(1000);
  const [nearby, setNearby] = useState([]), [nearbyBusy, setNearbyBusy] = useState(false), [nearbyError, setNearbyError] = useState('');
  const [journeys, setJourneys] = useState(null), [journeyBusy, setJourneyBusy] = useState(false), [journeyError, setJourneyError] = useState('');
  const recommendedOptions=useMemo(()=>walkingRankedDistinctRoutes(journeys?.options||[],2),[journeys]);
  const [selectedStop, setSelectedStop] = useState(null), [selectedOption, setSelectedOption] = useState(null), [sampleStop, setSampleStop] = useState('');
  const [now, setNow] = useState(Date.now);
  const [page, setPage] = useState('Home');
  const [intent, setIntent] = useState('');
  const [routeSequence, setRouteSequence] = useState([]);
  const [routeGeometry,setRouteGeometry]=useState([]);
  const [comparisonSequences, setComparisonSequences] = useState([]);
  const [activeTripId, setActiveTripId] = useState('');
  const [catalogRoute,setCatalogRoute]=useState(null);
  const [intentData,setIntentData]=useState(()=>parseJourneyIntent(''));
  const [parsedOrigin,setParsedOrigin]=useState(null);
  const [intentResolution,setIntentResolution]=useState('');
  const [originMatches,setOriginMatches]=useState([]);
  const [destinationMatches,setDestinationMatches]=useState([]);
  const [scheduleRows,setScheduleRows]=useState([]),[scheduleBusy,setScheduleBusy]=useState(false),[scheduleError,setScheduleError]=useState('');
  const [stopRouteSchedules,setStopRouteSchedules]=useState([]),[stopScheduleBusy,setStopScheduleBusy]=useState(false),[stopScheduleError,setStopScheduleError]=useState('');
  const connected = connection === 'live';
  useEffect(() => connectLive({ onState: setLive, onStatus: setConnection }), []);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const plannerPosition=useMemo(()=>parsedOrigin?{latitude:parsedOrigin.latitude,longitude:parsedOrigin.longitude}:gps.position,[parsedOrigin,gps.position]);
  const plannerRadius=parsedOrigin?35:radius;
  const plannerPreference=['faster','less_crowd','fewer_transfers'].includes(preference)?preference:undefined;
  useEffect(() => {
    if(!intentData.originQuery||!intentData.destinationQuery)return;
    const controller=new AbortController();
    setParsedOrigin(null);setDestination(null);setIntentResolution('Matching origin and destination against loaded GTFS stops…');
    Promise.all([api.search(intentData.originQuery,controller.signal),api.search(intentData.destinationQuery,controller.signal)]).then(([originData,destinationData])=>{
      const exact=(data,q)=>data.stops.find(stop=>stop.stop_name.trim().toLocaleLowerCase()===q.trim().toLocaleLowerCase()||stop.stop_id.trim().toLocaleLowerCase()===q.trim().toLocaleLowerCase());
      const origin=exact(originData,intentData.originQuery)|| (originData.stops.length===1?originData.stops[0]:null),dest=exact(destinationData,intentData.destinationQuery)||(destinationData.stops.length===1?destinationData.stops[0]:null);
      setParsedOrigin(origin);setDestination(dest);setOriginMatches(origin?[]:originData.stops);setDestinationMatches(dest?[]:destinationData.stops);
      if(origin&&dest)setIntentResolution(`Matched both places to GTFS stops${catalog?.data_source==='SAMPLE'?' · SAMPLE feed':''}.`);
      else setIntentResolution('Choose the matching GTFS stop for each place. BusSure will plan only after both are resolved.');
    }).catch(error=>{if(error.name!=='AbortError')setIntentResolution(error.message);});
    return()=>controller.abort();
  },[intentData,catalog]);
  useEffect(() => {
    let active = true;
    Promise.all([api.health(), api.catalog()]).then(([h, c]) => { if (active) { setHealth(h); setCatalog(c); setSampleStop(previous => previous || c.stops[0]?.stop_id || ''); setCatalogError(''); } }).catch(err => { if (active) setCatalogError(err.message); });
    return () => { active = false; };
  }, [connected, live.epoch]);
  useEffect(() => {
    setNearby([]); setSelectedStop(null); setSelectedOption(null);
    if (!gps.position) return;
    const controller = new AbortController(); setNearbyBusy(true); setNearbyError('');
    api.nearby(gps.position, radius, controller.signal).then(data => { setNearby(data); setSelectedStop(current => current || data[0] || null); setNearbyBusy(false); }).catch(err => { if (err.name !== 'AbortError') { setNearbyError(err.message); setNearbyBusy(false); } });
    return () => controller.abort();
  }, [gps.position, radius, live.epoch]);
  useEffect(() => {
    setJourneys(null); setSelectedOption(null); setJourneyError(''); setJourneyBusy(false);
    if (!plannerPosition || !destination) return;
    const controller = new AbortController(); setJourneyBusy(true);
    api.journeys(plannerPosition, destination.stop_id, plannerRadius, plannerPreference, controller.signal).then(data => { setJourneys(data); setJourneyBusy(false); }).catch(err => { if (err.name !== 'AbortError') { setJourneyError(err.message); setJourneyBusy(false); } });
    return () => controller.abort();
  }, [plannerPosition, destination, plannerRadius, plannerPreference, live.epoch]);
  useEffect(() => {
    let active = true;
    const options = recommendedOptions;
    if (options.length < 2) { setComparisonSequences([]); return () => { active = false; }; }
    Promise.all(options.map(async (option,index) => {
      const tripId = option.eligible_trip_segments?.[0]?.trip_id;
      if (!tripId) return null;
      const data = await api.tripStops(tripId);
      const sequence = data.stops.map(row=>({...stops[row.stop_id],...row})).filter(stop=>Number.isFinite(stop.latitude)&&Number.isFinite(stop.longitude));
      return {id:option.option_id,stops:sequence,geometry:data.shape||[],color:index===0?'#176b5b':'#7188bb'};
    })).then(data=>{if(active)setComparisonSequences(data.filter(Boolean));}).catch(()=>{if(active)setComparisonSequences([]);});
    return () => { active = false; };
  }, [recommendedOptions, catalog]);
  const stops = useMemo(() => Object.fromEntries((catalog?.stops || []).map(stop => [stop.stop_id, stop])), [catalog]);
  const routes = useMemo(() => Object.fromEntries((catalog?.routes || []).map(route => [route.route_id, route])), [catalog]);
  const events = activeEvents(live.events, now);
  const staleSeconds = health?.stale_seconds || 45;
  const liveCount = Object.values(live.buses).filter(bus => !isStale(bus, now, staleSeconds)).length;
  const staleCount = Object.keys(live.buses).length - liveCount;
  const selectedJourney = journeys?.options.find(option => option.option_id === selectedOption);
  const nearestLiveBuses = nearby[0] ? Object.values(live.buses).filter(bus => !isStale(bus, now, staleSeconds) && (bus.current_stop_id === nearby[0].stop_id || bus.next_stop_id === nearby[0].stop_id)) : [];
  const nearestSchedule = nearby[0]?.stop_id === selectedStop?.stop_id ? stopRouteSchedules[0] : null;
  useEffect(()=>{
    if(page!=='Timetable'){return;}
    const routeId=selectedJourney?.route.route_id||catalogRoute?.route_id;
    const stopId=selectedJourney?.origin_stop.stop_id||routeSequence[0]?.stop_id;
    if(!routeId){setScheduleRows([]);return;}
    const controller=new AbortController();setScheduleBusy(true);setScheduleError('');
    api.routeTimetable(routeId,stopId,controller.signal).then(data=>{setScheduleRows(data.schedules);setScheduleBusy(false);}).catch(error=>{if(error.name!=='AbortError'){setScheduleError(error.message);setScheduleBusy(false);}});
    return()=>controller.abort();
  },[page,selectedJourney,catalogRoute,routeSequence]);
  useEffect(()=>{
    if(!selectedStop?.stop_id){setStopRouteSchedules([]);return;}
    const controller=new AbortController();setStopScheduleBusy(true);setStopScheduleError('');
    api.stopRoutes(selectedStop.stop_id,controller.signal).then(async data=>{
      const services=await Promise.all(data.routes.map(async route=>({route,data:await api.routeTimetable(route.route_id,selectedStop.stop_id,controller.signal)})));
      setStopRouteSchedules(services.map(({route,data:feed})=>({route,schedules:feed.schedules})));setStopScheduleBusy(false);
    }).catch(error=>{if(error.name!=='AbortError'){setStopScheduleError(error.message);setStopScheduleBusy(false);}});
    return()=>controller.abort();
  },[selectedStop?.stop_id]);
  function chooseOption(option) { setSelectedOption(option.option_id); setSelectedStop(option.origin_stop); }
  async function openRoute(option) {
    chooseOption(option); setCatalogRoute(null); setPage('Route Details'); setRouteSequence([]);setRouteGeometry([]);
    const segment = option.eligible_trip_segments?.[0];
    if (!segment?.trip_id) return;
    setActiveTripId(segment.trip_id);
    try { const result = await api.tripStops(segment.trip_id); setRouteSequence(result.stops.map(row=>({...stops[row.stop_id],...row})).filter(stop=>Number.isFinite(stop.latitude)&&Number.isFinite(stop.longitude)));setRouteGeometry(result.shape||[]); }
    catch (error) { setJourneyError(error.message); }
  }
  async function openCatalogRoute(route) {
    setCatalogRoute(route);setSelectedOption(null);setRouteSequence([]);setRouteGeometry([]);setJourneyError('');
    try { const detail=await api.routeInfo(route.route_id);const tripId=detail.trip_ids?.[0];if(!tripId){setCatalogRoute(null);setActiveTripId('');return;}setActiveTripId(tripId);const data=await api.tripStops(tripId);setRouteSequence(data.stops.map(row=>({...stops[row.stop_id],...row})).filter(stop=>Number.isFinite(stop.latitude)&&Number.isFinite(stop.longitude)));setRouteGeometry(data.shape||[]); }
    catch(error){setJourneyError(error.message);}
  }
  function interpretIntent(text) {
    const parsed=parseJourneyIntent(text);
    setIntentData(parsed);
    setPreference(parsed.priority||(/\b(reliable|reliability)\b/i.test(text)?'reliable':/\b(less walking|shorter walk)\b/i.test(text)?'less_walking':''));
    if(!parsed.originQuery||!parsed.destinationQuery){setParsedOrigin(null);setOriginMatches([]);setDestinationMatches([]);if(intentData.originQuery||intentData.destinationQuery)setDestination(null);setIntentResolution('Add a “from … to …” request to plan by named stops.');}
  }
  return <div className={`app-shell app-page-${page.toLowerCase().replaceAll(' ','-')}`}>
    <header className="app-header"><a className="brand" href="/" aria-label="BusSure home"><span className="brand-icon">↗</span><span>Bus<span className="brand-light">Sure</span><small>JOURNEY ASSISTANT</small></span></a><nav className="app-nav" aria-label="Main navigation">{['Home','AI Journey','Live Map','Nearby Stops','Routes','Timetable','My Journey','Simulation Studio','Model Insights'].map(item=><button key={item} className={page===item?'active':''} onClick={()=>setPage(item)}>{item}</button>)}</nav><div className="header-right"><span className={`connection-badge ${connected ? '' : 'disconnected'}`}><span className="live-dot"/>{connected ? 'GPS connected' : connection}</span><DevBeezLogo /></div></header>
    <div className="workspace"><aside className="sidebar"><div className="intro"><span className="eyebrow">A LITTLE CLARITY FOR YOUR COMMUTE</span><h1>Your next journey.<br/><span>In view.</span></h1><p>Find a stop. Explore your routes.<br/>See where the buses are.</p></div><section className="quick-access"><span className="eyebrow">QUICK ACCESS</span><div>{[['AI Journey','✳'],['Nearby Stops','◎'],['Live Map','⌖'],['Routes','↗']].map(([label,icon])=><button key={label} onClick={()=>setPage(label)}><span>{icon}</span>{label}</button>)}</div></section>
      {catalog?.data_source === 'SAMPLE' && <div className="sample-banner"><strong>SAMPLE DATA</strong><span>Fictional routes for testing. Not real Chennai services.</span></div>}
      {catalogError && <p className="error-message" role="alert">{catalogError}</p>}
      <section className="location-panel"><div className="row"><span className="eyebrow">YOUR STARTING POINT</span><span className="permission">GPS: {gps.permission}</span></div><button className="location-button" onClick={gps.locate} disabled={gps.locating}><span aria-hidden="true">⌖</span>{gps.locating ? 'Finding your location…' : 'Use my current location'}</button>
        {gps.error && <p className="error-message" role="alert">{gps.error}</p>}
        {gps.position && <p className="location-status" data-testid="passenger-location">{gps.position.source === 'sample' ? 'SAMPLE origin · not device GPS' : 'Device location found'}{gps.position.accuracy !== null && ` · ±${Math.round(gps.position.accuracy)} m`}{gps.position.accuracy > 100 && ' · weak accuracy'}<small>{gps.position.latitude.toFixed(5)}, {gps.position.longitude.toFixed(5)}</small></p>}
      </section>
      <DestinationSearch value={destination} onSelect={setDestination} disabled={!catalog}/>
      <div className="search-options"><label>Preference <span>optional</span><select value={preference} onChange={e => setPreference(e.target.value)}><option value="">No preference</option><option value="faster">Faster journey</option><option value="less_crowd">Less crowd</option><option value="fewer_transfers">Fewer transfers</option></select></label><label>Walking radius<select value={radius} onChange={e => setRadius(Number(e.target.value))}><option value={500}>500 m</option><option value={1000}>1 km</option><option value={2000}>2 km</option><option value={5000}>5 km</option></select></label></div>
      {preference && <p className="model-notice">{preference === 'fewer_transfers' ? 'Only direct routes are supported; no preference ranking is applied.' : 'Prediction model not connected yet. This preference is not applied.'}</p>}
      <NearbyStops stops={nearby} busy={nearbyBusy} error={nearbyError} selected={selectedStop} onSelect={stop => { setSelectedStop(stop); setSelectedOption(null); }}/>
      {catalog?.data_source === 'SAMPLE' && <details className="sample-tools"><summary>Try a sample journey</summary><p>If your actual GPS is outside the fictional stop area, choose a clearly labelled test origin.</p><select aria-label="Sample origin stop" value={sampleStop} onChange={e => setSampleStop(e.target.value)}>{catalog.stops.map(stop => <option key={stop.stop_id} value={stop.stop_id}>{stop.stop_name}</option>)}</select><button className="text-button" onClick={() => { if (stops[sampleStop]) gps.useSample(stops[sampleStop]); }}>Use SAMPLE origin</button></details>}
      <p className="sidebar-footer">Your passenger location is never sent as a bus update.</p>
    </aside>
    <main className={`main-content page-${page.toLowerCase().replaceAll(' ','-')}`}>
      <AIWorkspace page={page} live={live} connected={connected} gps={gps} now={now} staleSeconds={staleSeconds} onNavigate={setPage}/>{page === 'AI Journey' && <><details><summary>Earlier baseline planner</summary><SyntheticJourney/></details><details><summary>Fictional presentation scenarios</summary><DemoJourneyQuestion /></details><details><summary>Technical appendix: historical DCRNN model (separate from this demo)</summary><HistoricalModelDemo /></details></>}
    {page==='AI Journey'&&<details><summary>Legacy GTFS intent search</summary><section className="ai-intro"><span className="eyebrow">YOUR JOURNEY, YOUR PRIORITIES</span><h1>Where would you like to go?</h1><p>Describe what matters. BusSure resolves place names against loaded GTFS before planning.</p><textarea aria-label="Describe your journey" placeholder="From Guindy to T. Nagar. I want less crowd and don't make me wait too long." value={intent} onChange={e=>{setIntent(e.target.value);interpretIntent(e.target.value)}}/>{intentData.originQuery&&intentData.destinationQuery&&<div className={`intent-resolution ${parsedOrigin&&destination?'matched':''}`}>{intentResolution}{parsedOrigin&&destination&&<small>Planning origin: {parsedOrigin.stop_name} · {catalog?.data_source==='SAMPLE'?'SAMPLE GTFS':'GTFS'}</small>}</div>}{originMatches.length>0&&<div className="intent-suggestions"><b>Choose origin stop</b>{originMatches.slice(0,5).map(stop=><button key={stop.stop_id} onClick={()=>{setParsedOrigin(stop);setOriginMatches([]);setIntentResolution(destination?'Both stops resolved against GTFS.':'Choose the destination stop to continue.')}}>{stop.stop_name}<small>{stop.stop_id}</small></button>)}</div>}{destinationMatches.length>0&&<div className="intent-suggestions"><b>Choose destination stop</b>{destinationMatches.slice(0,5).map(stop=><button key={stop.stop_id} onClick={()=>{setDestination(stop);setDestinationMatches([]);setIntentResolution(parsedOrigin?'Both stops resolved against GTFS.':'Choose the origin stop to continue.')}}>{stop.stop_name}<small>{stop.stop_id}</small></button>)}</div>}<div className="preference-chips">{[['Fastest','faster'],['Low crowd','less_crowd'],['Most reliable','reliable'],['Fewer transfers','fewer_transfers'],['Less walking','less_walking'],['Leave now','']].map(([label,key])=><button className={preference===key&&key?'chosen':''} key={label} onClick={()=>setPreference(key)}>{label}</button>)}</div>{intentData.maxWaitMinutes!==null&&<p className="model-notice">Maximum wait of {intentData.maxWaitMinutes} minutes understood; the current planner does not filter options by wait time.</p>}{intentData.unsupportedPriority&&<p className="model-notice">{intentData.unsupportedPriority}</p>}<p className="scope-note">Preferences are interpreted deterministically. Only verified GTFS stops and schedules supply route facts. This legacy view uses GTFS connectivity only. Use the integrated planner above for model-based recommendations.</p></section></details>}
    {page==='Home'&&<section className="nearest-stop-card"><div className="nearest-stop-heading"><span className="eyebrow">NEAREST BUS STOP</span>{nearbyBusy?<><i className="skeleton-line wide"/><i className="skeleton-line short"/></>:nearby[0]?<><h3>{nearby[0].stop_name}</h3><p>{nearby[0].estimated_walking_minutes.toFixed(1)} min walk · {Math.round(nearby[0].distance_meters)} m</p><div className="nearest-service">{nearestLiveBuses.length?<span className="service-status live"><i className="live-dot"/>{nearestLiveBuses.length} live {nearestLiveBuses.length===1?'bus':'buses'}</span>:<span className="service-status">No live buses confirmed</span>}{nearestSchedule&&<span className="nearest-route"><b>{nearestSchedule.route.route_short_name||nearestSchedule.route.route_id}</b><small>To {nearestSchedule.schedules[0]?.destination_stop_name||nearestSchedule.route.route_long_name||'route details'}</small></span>}</div></>:<p>Use your location to find nearby stops.</p>}</div>{nearby[0]&&<div className="nearest-actions"><button onClick={()=>{setSelectedStop(nearby[0]);setPage('Nearby Stops')}}>Stop details <span>→</span></button>{nearestSchedule&&<button className="secondary" onClick={()=>{setCatalogRoute(nearestSchedule.route);setPage('Timetable')}}>View timetable <span>→</span></button>}</div>}{catalog?.data_source==='SAMPLE'&&<span className="sample-mini">SAMPLE</span>}</section>}
    {(page==='Home'||page==='Live Map'||page==='Nearby Stops'||page==='Route Details'||page==='Timetable'||(page==='Routes'&&catalogRoute)||(page==='My Journey'&&selectedJourney))&&<section className={`map-section ${page==='Route Details'||page==='Routes'||page==='My Journey'?'route-map-section':''}`}><div className="map-heading">{page==='Route Details'&&<button className="route-back-button" onClick={()=>setPage('AI Journey')} aria-label="Back to journey options">←</button>}<div><span className="eyebrow">{(page==='Route Details'||page==='Routes'&&catalogRoute||page==='My Journey')?'GTFS TRIP · '+(activeTripId||''):'ON THE NETWORK'}</span><h2>{page==='Nearby Stops'?'Stops around you':page==='Home'||page==='Live Map'?'Buses around you':page==='AI Journey'?'Compare options on the map':page==='Route Details'?(selectedJourney?`${selectedJourney.route.route_short_name||selectedJourney.route.route_id} · ${selectedJourney.route.route_long_name}`:'Route details'):page==='Routes'&&catalogRoute?`${catalogRoute.route_short_name||catalogRoute.route_id} · ${catalogRoute.route_long_name}`:page==='My Journey'&&selectedJourney?`${selectedJourney.route.route_short_name||selectedJourney.route.route_id} · Your route`: 'On the network'}</h2></div><div className="map-counts"><span><strong>{liveCount}</strong> fresh fixes</span><span><strong>{staleCount}</strong> stale</span></div></div>
      <MapView position={gps.position} stops={nearby} buses={live.buses} events={events} routes={routes} allStops={stops} selected={selectedStop} destination={selectedJourney?.destination_stop || destination} now={now} staleSeconds={staleSeconds} fallback={catalog?.data_source==='SAMPLE'?catalog?.stops[0]:CHENNAI_CENTER} connected={connected} routeSequence={(page==='Route Details'||page==='Timetable'||page==='Routes'&&catalogRoute||page==='My Journey'&&selectedJourney)?routeSequence:EMPTY_ARRAY} routeGeometry={(page==='Route Details'||page==='Timetable'||page==='Routes'&&catalogRoute||page==='My Journey'&&selectedJourney)?routeGeometry:EMPTY_ARRAY} routeSequences={page==='AI Journey'?comparisonSequences:EMPTY_ARRAY} selectedOption={selectedOption} onStopSelect={stop=>setSelectedStop(stop)}/>
      {(routeSequence.length>1&&(page==='Route Details'||page==='Timetable'||page==='Routes'||page==='My Journey'))&&<p className="geometry-source-note">{routeGeometry.length>1?'Route outline from GTFS shape geometry.':'GTFS shape geometry unavailable; dashed line connects ordered GTFS stops.'}</p>}{page==='AI Journey'&&comparisonSequences.length>0&&<p className="geometry-source-note">Routes use GTFS shapes where provided; dashed paths show stop-to-stop outlines when shape geometry is unavailable.</p>}
      <div className="map-caption"><span>SIMULATOR markers are test vehicles, never official live MTC/TNSTC buses.</span><span>{events.length} active network {events.length === 1 ? 'event' : 'events'}</span></div>
    </section>}
    {events.length > 0 && <section className="event-strip" aria-label="Network events">{events.map(event => <div key={event.event_id} data-testid="network-event"><b>! {event.event_type.replaceAll('_', ' ')}</b><span>{event.description}</span>{event.severity && <small>{event.severity}</small>}{event.route_id && <small>Route {event.route_id}</small>}</div>)}</section>}
    {page==='My Journey'&&selectedJourney&&<MyJourneyPanel journey={selectedJourney} sequence={routeSequence} tripId={activeTripId} dataSource={catalog?.data_source} onOpen={()=>setPage('AI Journey')} onTimetable={()=>setPage('Timetable')}/> }
    {page==='Routes'&&<RoutesDirectory catalog={catalog} selected={catalogRoute} stops={stops} tripId={activeTripId} sequence={routeSequence} error={journeyError} onSelect={openCatalogRoute} onTimetable={()=>setPage('Timetable')}/>}
    {page==='Timetable'&&catalogRoute&&<section className="route-detail-panel catalog-timetable"><div className="route-detail-heading"><div><span className="eyebrow">{catalog?.data_source==='SAMPLE'?'SAMPLE GTFS SCHEDULE':'GTFS SCHEDULE'}</span><h2>Timetable · {catalogRoute.route_short_name||catalogRoute.route_id}</h2><p>{catalogRoute.route_long_name}</p></div><button className="route-details-button" onClick={()=>setPage('Routes')}>Back to routes <span>←</span></button></div><p className="schedule-source">Scheduled GTFS departures at the selected boarding stop. Service calendars aren’t evaluated; predictions await model integration.</p>{scheduleBusy?<p className="muted">Loading GTFS departures…</p>:scheduleError?<p role="alert" className="error-message">{scheduleError}</p>:scheduleRows.length?<ol className="schedule-list">{scheduleRows.map((row,index)=><li key={`${row.trip_id}-${index}`}><time>{row.departure_time||row.arrival_time||'Time unavailable'}</time><span>{stops[row.stop_id]?.stop_name||row.stop_id}<small>Trip {row.trip_id} · service {row.service_id}</small></span></li>)}</ol>:<p className="muted">No GTFS departures are available for this stop.</p>}</section>}
    {(page==='Route Details'||page==='Timetable')&&selectedJourney&&<section className="route-detail-panel"><div className="route-detail-heading"><div><span className="eyebrow">{catalog?.data_source==='SAMPLE'?'SAMPLE GTFS':'GTFS ROUTE'}</span><h2>{page==='Timetable'?'Timetable':selectedJourney.route.route_short_name||selectedJourney.route.route_id}</h2><p>{selectedJourney.origin_stop.stop_name} <span>→</span> {selectedJourney.destination_stop.stop_name}</p></div><button className="route-details-button" onClick={()=>setPage(page==='Timetable'?'Route Details':'Timetable')}>{page==='Timetable'?'Back to route':'View timetable'} <span>→</span></button></div>{page==='Timetable'?<><p className="schedule-source">GTFS scheduled departures at {selectedJourney.origin_stop.stop_name}. Service calendars are not evaluated; predicted arrival is awaiting model integration.</p><ol className="schedule-list">{scheduleRows.map((row,index)=><li key={`${row.trip_id}-${index}`}><time>{row.departure_time||row.arrival_time||'Time unavailable'}</time><span>{stops[row.stop_id]?.stop_name||row.stop_id}<small>Trip {row.trip_id}</small></span></li>)}</ol></>:<><div className="route-facts"><span>{routeSequence.length} stops in selected trip</span><span>{connected?'Live bus feed connected':'Live feed reconnecting'}</span><span>ETA · Crowd · Reliability awaiting models</span></div><RouteStopTimeline sequence={routeSequence} boardingStopId={selectedJourney.origin_stop.stop_id} destinationStopId={selectedJourney.destination_stop.stop_id} buses={live.buses} tripId={activeTripId} now={now} staleSeconds={staleSeconds}/><button className="route-details-button" onClick={()=>setPage('Timetable')}>View timetable <span>→</span></button></>}</section>}
    {page==='Nearby Stops'&&<section className="nearby-page"><div className="nearby-page-heading">{selectedStop&&<button className="nearby-back-button" onClick={()=>setSelectedStop(null)} aria-label="Show all nearby stops">←</button>}<div><span className="eyebrow">WALKABLE CONNECTIONS</span><h2>{selectedStop?selectedStop.stop_name:'Nearby stops'}</h2></div>{selectedStop&&<button className="nearby-all-button" onClick={()=>setSelectedStop(null)}>See all stops</button>}</div>{!selectedStop&&<p>Choose a stop marker or list item to see confirmed buses and scheduled services.</p>}{(!selectedStop?nearby:[]).map(stop=><button className="stop-row" key={stop.stop_id} onClick={()=>setSelectedStop(stop)}><span className="stop-dot"/><span className="stop-copy"><strong>{stop.stop_name}</strong><small>{Math.round(stop.distance_meters)} m away</small></span><span className="walk-time">{stop.estimated_walking_minutes.toFixed(1)} min walk</span></button>)}{!nearby.length&&!nearbyBusy&&<p className="muted">Use your location to find nearby bus stops.</p>}{selectedStop&&<div className="stop-detail-sheet"><div><span className="eyebrow">{selectedStop.estimated_walking_minutes!==undefined?'NEAREST BUS STOP':'BUS STOP'}</span><h3>{selectedStop.stop_name}</h3><p>{selectedStop.estimated_walking_minutes!==undefined?`${selectedStop.estimated_walking_minutes.toFixed(1)} min walk · ${Math.round(selectedStop.distance_meters)} m`:selectedStop.stop_id}</p></div><h4>Live buses at this stop</h4>{Object.values(live.buses).filter(bus=>!isStale(bus,now,staleSeconds)&&(bus.current_stop_id===selectedStop.stop_id||bus.next_stop_id===selectedStop.stop_id)).map(bus=><div className="stop-live-bus" key={bus.bus_id}><b>{routes[bus.route_id]?.route_short_name||bus.route_id}</b><span>{bus.current_stop_id===selectedStop.stop_id?'At stop':'Next stop'}</span><small>{bus.source==='SIMULATOR'?'SIMULATED':'LIVE PHONE GPS'}</small></div>)}{!Object.values(live.buses).some(bus=>!isStale(bus,now,staleSeconds)&&(bus.current_stop_id===selectedStop.stop_id||bus.next_stop_id===selectedStop.stop_id))&&<p className="no-live-buses">No live buses confirmed at this stop.</p>}<section className="stop-schedules"><h4>Scheduled services <small>· service calendars not checked</small></h4>{stopScheduleBusy?<p className="muted">Loading GTFS stop times…</p>:stopScheduleError?<p role="alert" className="error-message">{stopScheduleError}</p>:stopRouteSchedules.length?stopRouteSchedules.map(({route,schedules})=><article className="stop-schedule-route" key={route.route_id}><div><b>{route.route_short_name||route.route_id}</b><span>{route.route_long_name||'GTFS route'}</span></div>{schedules.slice(0,3).map((trip,index)=><p key={`${trip.trip_id}-${index}`}><time>{trip.departure_time||trip.arrival_time||'Time unavailable'}</time><span>To {trip.destination_stop_name}</span></p>)}</article>):<p className="muted">No scheduled route departures are available for this stop.</p>}</section><span className="gtfs-source-chip">{catalog?.data_source==='SAMPLE'?'SAMPLE GTFS':'GTFS stop data'}</span></div>}</section>}
    </main></div><footer className="app-footer">BusSure <span>GPS + GTFS passenger preview · Built for clearer journeys</span></footer>
  </div>;
}
