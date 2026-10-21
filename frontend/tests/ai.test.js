import { test } from 'node:test';
import assert from 'node:assert/strict';
import { aiRequest, plannerPayload } from '../src/services/ai.js';
test('planner builds a timezone-explicit transfer request',()=>{
  const b=plannerPayload({origin:'MAD',destination:'KAN',date:'2026-10-17',time:'08:00',preference:'less_crowd',maxTransfers:'2',buffer:'5',useLocation:false});
  assert.equal(b.departure_time,'2026-10-17T08:00:00+05:30');assert.equal(b.max_transfers,2);assert.equal(b.transfer_buffer,5);
});
test('coordinate origin does not also submit stop origin',()=>{
  const b=plannerPayload({useLocation:true,destination:'CEN',date:'2026-10-17',time:'08:00',maxTransfers:1,buffer:5},{latitude:12.965,longitude:80.198});
  assert.equal(b.latitude,12.965);assert.equal(b.origin,undefined);
});
test('API wrapper submits JSON and reports backend failures',async()=>{
  const original=globalThis.fetch;
  try{
    globalThis.fetch=async(path,o)=>{assert.equal(path,'/api/ai/journeys');assert.equal(o.method,'POST');assert.deepEqual(JSON.parse(o.body),{origin:'MAD'});return {ok:true,json:async()=>({options:[]})};};
    assert.deepEqual(await aiRequest('/api/ai/journeys',{origin:'MAD'}),{options:[]});
    globalThis.fetch=async()=>({ok:false,status:409,json:async()=>({detail:'Restart with synthetic network'})});
    await assert.rejects(aiRequest('/api/ai/journeys',{}),/Restart with synthetic network/);
    globalThis.fetch=async()=>({ok:false,status:422,json:async()=>({detail:[{}]})});
    await assert.rejects(aiRequest('/api/ai/journeys',{}),/Check your inputs/);
  }finally{globalThis.fetch=original;}
});
