import { isStale } from '../services/journey.js';

export default function RouteStopTimeline({ sequence, boardingStopId, destinationStopId, buses, tripId, now, staleSeconds }) {
  const tripBuses=Object.values(buses).filter(bus=>bus.trip_id===tripId&&bus.route_verified&&!isStale(bus,now,staleSeconds)&&Number.isInteger(bus.stop_sequence_index));
  const bus=tripBuses.sort((a,b)=>b.stop_sequence_index-a.stop_sequence_index)[0];
  return <>
    {bus&&<div className="timeline-live-status"><span className="live-dot"/><div><b>{bus.bus_id} is on this trip</b><small>{bus.source==='SIMULATOR'?'SIMULATED':'LIVE PHONE GPS'} · {bus.current_stop_id?'Current: '+(sequence.find(stop=>stop.stop_id===bus.current_stop_id)?.stop_name||bus.current_stop_id):'Position matched to trip'}{bus.next_stop_id?' · Next: '+(sequence.find(stop=>stop.stop_id===bus.next_stop_id)?.stop_name||bus.next_stop_id):''}</small></div></div>}
    <ol className="route-timeline">{sequence.map((stop,index)=>{const current=bus?.stop_sequence_index===index;const next=bus?.stop_sequence_index+1===index;return <li className={`${index===0?'route-start':''} ${index===sequence.length-1?'route-end':''} ${stop.stop_id===boardingStopId?'boarding-stop':''} ${current?'bus-current':''} ${next?'bus-next':''}`} key={`${stop.stop_id}-${index}`}><span className="timeline-node"/><div><b>{stop.stop_name}</b>{current&&<small>Bus currently here</small>}{next&&<small>Bus next stop</small>}{stop.stop_id===boardingStopId&&<small>Nearest boarding stop</small>}{stop.stop_id===destinationStopId&&<small>Your destination</small>}</div><time>{stop.departure_time||stop.arrival_time||''}</time></li>;})}</ol>
    {!bus&&<p className="no-live-buses">No live bus progress confirmed for this GTFS trip.</p>}
  </>;
}
