import React from 'react';
import { distanceMeters, isStale, routeLabel, stopLabel } from '../services/journey.js';

const fields = ['Wait', 'ETA', 'Crowd', 'Delay risk', 'Reliability'];

export default function LiveTwoBusComparison({ options, live, stops, connected, now, staleSeconds, radius }) {
  if (!options?.length) return null;
  return <section className="live-compare" aria-label="Live journey comparison">
    <div className="live-compare-heading"><div><span className="eyebrow">LIVE COMPARISON</span><h3>Follow both options</h3></div><span className={`connection-badge ${connected?'':'disconnected'}`}><span className="live-dot"/>{connected?'Live feed connected':'Reconnecting'}</span></div>
    <div className="live-compare-grid">{options.slice(0,2).map((option,index)=>{
      const candidates=Object.values(live.buses).filter(bus=>bus.route_verified&&bus.route_id===option.route.route_id&&!isStale(bus,now,staleSeconds)&&bus.stop_sequence_index!==null&&option.eligible_trip_segments.some(segment=>segment.trip_id===bus.trip_id&&(bus.stop_sequence_index<segment.boarding_index||(bus.stop_sequence_index===segment.boarding_index&&distanceMeters(bus,option.origin_stop)<=radius))));
      return <article className="live-compare-card" key={option.option_id}><div className="live-card-title"><span>OPTION {index?'B':'A'}</span><b>{routeLabel(option.route)}</b><small>{option.origin_stop.stop_name}</small></div>{candidates.length?candidates.map(bus=><div className="candidate-bus" key={bus.bus_id}><div className="candidate-head"><b>{bus.bus_id}</b><span className={`source-tag ${bus.source==='SIMULATOR'?'sim':''}`}>{bus.source==='SIMULATOR'?'SIMULATED':'LIVE PHONE GPS'}</span></div><dl><dt>Current stop</dt><dd>{stopLabel(bus.current_stop_id,stops)}</dd><dt>Next stop</dt><dd>{stopLabel(bus.next_stop_id,stops)}</dd><dt>To boarding</dt><dd>{Math.round(distanceMeters(bus,option.origin_stop))} m straight line</dd>{fields.map(field=><React.Fragment key={field}><dt>{field}</dt><dd className="pending-value">{field==='Wait'?'Scheduled data pending':'Model pending'}</dd></React.Fragment>)}</dl></div>):<p className="no-live-buses">No eligible live bus confirmed. GTFS route availability does not guarantee service now.</p>}</article>;
    })}</div><p className="recommendation-note">BusSure will update its recommendation when comparable verified values are available. No predicted changes are shown before model integration.</p>
  </section>;
}
