import { routeLabel } from './journey.js';

// Rank only on a measured, available field. Do not infer total duration or ML scores.
export function walkingRankedDistinctRoutes(options = [], limit = 2) {
  const ranked=[...options].sort((a,b)=>{
    const aWalk=Number(a.origin_stop?.estimated_walking_minutes),bWalk=Number(b.origin_stop?.estimated_walking_minutes);
    return aWalk-bWalk||routeLabel(a.route).localeCompare(routeLabel(b.route))||String(a.option_id).localeCompare(String(b.option_id));
  });
  const seen=new Set();
  return ranked.filter(option=>{
    const routeId=option.route?.route_id;
    if(!routeId||seen.has(routeId))return false;
    seen.add(routeId);return true;
  }).slice(0,limit);
}
