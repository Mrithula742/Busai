import test from 'node:test';
import assert from 'node:assert/strict';
import { demoPoints, demoPosition } from '../src/services/demoMap.js';
test('demo anchors cover both scenarios without inventing unknown coordinates',()=>{
  for (const stops of [['Madipakkam','Velachery','Guindy','T Nagar','Chennai Central'],['Chennai','Tambaram','Kanchipuram'],['Chennai','Demo interchange','Kanchipuram']]) assert.equal(demoPoints({stops}).length,stops.length);
  assert.deepEqual(demoPoints({stops:['Unknown']}),[]);
});
test('animation interpolates and loops without overflowing endpoints',()=>{
  const points=[[0,0],[10,20],[20,40]];
  assert.deepEqual(demoPosition(points,0.25),[5,10]);
  assert.deepEqual(demoPosition(points,1),[0,0]);
  assert.equal(demoPosition([],0),null);
});
