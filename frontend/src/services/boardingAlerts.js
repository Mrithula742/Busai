// Deterministic in-session alerts; no permission requests or network side effects here.
export function boardingAlerts({journey,vehicles=[],now,staleSeconds=45,connected,updated,sessionKey=''},memory) {
  const events=[];
  if(!journey || !connected || !Number.isFinite(Date.parse(updated)) || now-Date.parse(updated)>45000 || Date.parse(updated)>now+10000)return events;
  if(Date.parse(journey.arrival_time)<now)return events;
  const key=`${journey.option_id}:${sessionKey}`;
  const emit=(id,message,type,source)=>{const full=`${key}:${id}`;if(memory.seen.has(full))return;memory.seen.add(full);events.push({id:full,message,type,source,timestamp:now});};
  const fresh=vehicles.filter(v=>v.source==='REAL_PHONE_GPS'&&v.tracking_status==='FRESH'&&v.status!=='STALE'&&Number.isFinite(Date.parse(v.timestamp))&&now-Date.parse(v.timestamp)>=0&&now-Date.parse(v.timestamp)<staleSeconds*1000);
  const first=journey.legs[0];
  if(first && Math.abs(Date.parse(first.departure_time)-now)<=15*60000){
    for(const bus of fresh){
      if(bus.route_id===first.route_id && bus.boarding_eta_minutes!==null && bus.boarding_eta_minutes!==undefined && bus.boarding_eta_minutes>=0 && bus.boarding_eta_minutes<=3){
        emit(`approach:${bus.bus_id}:${first.stop_ids[0]}`,`${bus.bus_id} is estimated ${bus.boarding_eta_minutes.toFixed(1)} min from your boarding stop. Real phone GPS.`,'approaching',bus.source);
      }
    }
  }
  for(let i=0;i<journey.legs.length-1;i++){
    const leg=journey.legs[i],next=journey.legs[i+1];
    for(const bus of fresh){
      const matched=leg.bus?.bus_id===bus.bus_id || leg.trip_id===bus.trip_id;
      if(matched&&bus.route_id===leg.route_id&&bus.next_stop_id===leg.stop_ids.at(-1)&&bus.next_stop_eta_minutes!==null&&bus.next_stop_eta_minutes>=0&&bus.next_stop_eta_minutes<=3&&Math.abs(Date.parse(leg.arrival_time)-now)<=15*60000){
        emit(`transfer:${i}`,`Approaching ${leg.alighting_stop}. Prepare to transfer to ${next.route_id} at ${next.boarding_stop}.`,'transfer',bus.source);
      }
    }
  }
  return events;
}
