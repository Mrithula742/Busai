import {test} from 'node:test';
import assert from 'node:assert/strict';
import {boardingAlerts} from '../src/services/boardingAlerts.js';
const now=Date.parse('2026-10-17T08:00:00+05:30');
const iso=offset=>new Date(now+offset*60000).toISOString();
const memory=()=>({seen:new Set(),arrivals:new Map()});
const journey=()=>({option_id:'TEST',arrival_time:iso(60),legs:[{route_id:'A',trip_id:'A1',stop_ids:['S','T'],departure_time:iso(2),arrival_time:iso(20),alighting_stop:'Transfer',bus:{bus_id:'BUS'}},{route_id:'B',trip_id:'B1',stop_ids:['T','D'],boarding_stop:'Transfer'}]});
const vehicle=()=>({bus_id:'BUS',trip_id:'A1',route_id:'A',timestamp:iso(0),status:'MOVING',tracking_status:'FRESH',boarding_eta_minutes:2,next_stop_eta_minutes:2,next_stop_id:'T',source:'REAL_PHONE_GPS'});
const context=()=>({journey:journey(),vehicles:[vehicle()],now,staleSeconds:45,connected:true,updated:iso(0)});
test('approaching alert is source-labelled and deduplicated across fresh updates',()=>{const m=memory(),c=context();const first=boardingAlerts(c,m);assert.equal(first.length,1);assert.match(first[0].message,/Real phone GPS/);c.vehicles[0].timestamp=iso(.01);c.now+=1000;assert.equal(boardingAlerts(c,m).length,0);});
test('stale, future fixes, disconnected state and outdated plans suppress alerts',()=>{for(const change of [{connected:false},{updated:iso(-2)},{vehicles:[{...vehicle(),timestamp:iso(-2)}]},{vehicles:[{...vehicle(),timestamp:iso(2)}]},{vehicles:[{...vehicle(),tracking_status:'STALE'}]}])assert.equal(boardingAlerts({...context(),...change},memory()).length,0);});
test('synthetic vehicles and synthetic plan changes never trigger real alerts',()=>{const m=memory(),c=context();c.vehicles[0].source='SIMULATOR';assert.equal(boardingAlerts(c,m).length,0);c.journey.arrival_time=iso(67);c.updated=iso(.1);c.now+=6000;assert.equal(boardingAlerts(c,m).length,0);});
test('transfer reminder matches assigned bus or trip and imminent stop',()=>{const c=context();c.journey.legs[0].arrival_time=iso(2);const alerts=boardingAlerts(c,memory());assert.equal(alerts.filter(a=>a.type==='transfer').length,1);c.vehicles[0].bus_id='OTHER';c.vehicles[0].trip_id='OTHER';assert.equal(boardingAlerts(c,memory()).filter(a=>a.type==='transfer').length,0);});
test('completed journeys and future boarding windows do not trigger approaching alerts',()=>{const c=context();c.journey.arrival_time=iso(-1);assert.equal(boardingAlerts(c,memory()).length,0);c.journey.arrival_time=iso(60);c.journey.legs[0].departure_time=iso(40);assert.equal(boardingAlerts(c,memory()).length,0);});

test('a different departure session can receive a new boarding alert',()=>{const m=memory(),c=context();c.sessionKey='morning';assert.equal(boardingAlerts(c,m).length,1);assert.equal(boardingAlerts(c,m).length,0);c.sessionKey='evening';assert.equal(boardingAlerts(c,m).length,1);});
