import test from 'node:test';
import assert from 'node:assert/strict';
import { applyDelta, fromSnapshot, connectLive } from '../src/services/websocket.js';
import { activeEvents, relevantBuses, isStale } from '../src/services/journey.js';

test('snapshot plus deltas handles duplicates, gaps, restart and stale transitions', () => {
  let state = fromSnapshot({ epoch: 'one', revision: 5, buses: [], network_events: [] });
  const update = { epoch: 'one', revision: 6, bus: { bus_id: 'B', status: 'MOVING' } };
  state = applyDelta(state, update);
  assert.equal(applyDelta(state, update), state);
  state = applyDelta(state, { epoch: 'one', revision: 7, bus: { bus_id: 'B', status: 'STALE' } });
  assert.equal(state.buses.B.status, 'STALE');
  assert.throws(() => applyDelta(state, { epoch: 'one', revision: 9 }));
  assert.throws(() => applyDelta(state, { epoch: 'two', revision: 1 }));
});

test('journey eligibility filters trip direction, stale, passed and unknown progress', () => {
  const now = Date.now();
  const option = { route: { route_id: 'R' }, origin_stop: { latitude: 13, longitude: 80 }, eligible_trip_segments: [{ trip_id: 'T', boarding_index: 1, destination_index: 2 }] };
  const bus = { bus_id: 'one', route_id: 'R', trip_id: 'T', route_verified: true, latitude: 13, longitude: 80, timestamp: new Date(now).toISOString(), stop_sequence_index: 0, status: 'MOVING' };
  const buses = Object.fromEntries([bus, { ...bus, bus_id: 'two' }, { ...bus, bus_id: 'reverse', trip_id: 'REVERSE' }, { ...bus, bus_id: 'past', stop_sequence_index: 2 }, { ...bus, bus_id: 'left', stop_sequence_index: 1, longitude: 80.1 }, { ...bus, bus_id: 'unknown', stop_sequence_index: null }, { ...bus, bus_id: 'old', timestamp: new Date(now - 60000).toISOString() }].map(b => [b.bus_id, b]));
  assert.deepEqual(relevantBuses(option, buses, now, 45, 40).map(b => b.bus_id), ['one', 'two']);
  assert.equal(isStale(bus, now + 46000, 45), true);
});

test('scheduled, cleared and expired network events stay off the map', () => {
  const now = Date.now(), start = new Date(now - 1000).toISOString();
  const events = { active: { status: 'ACTIVE', start_time: start }, cleared: { status: 'CLEARED', start_time: start }, future: { status: 'ACTIVE', start_time: new Date(now + 10000).toISOString() }, expired: { status: 'ACTIVE', start_time: start, end_time: start } };
  assert.equal(activeEvents(events, now).length, 1);
});

test('socket queues deltas during snapshot and honors resync control', async () => {
  let socket, resolveSnapshot, calls = 0, latest;
  class FakeSocket {
    constructor() { socket = this; this.readyState = 1; }
    close() { this.readyState = 3; this.onclose?.(); }
    message(data) { this.onmessage({ data: JSON.stringify(data) }); }
  }
  const stop = connectLive({ Socket: FakeSocket, url: 'ws://test', onState: state => { latest = state; }, onStatus() {}, snapshot: () => {
    calls++;
    return new Promise(resolve => { resolveSnapshot = resolve; });
  } });
  const flush = () => new Promise(resolve => setImmediate(resolve));
  socket.message({ type: 'ready' }); await flush();
  socket.message({ type: 'BUS_LOCATION_UPDATED', epoch: 'A', revision: 1, bus: { bus_id: 'B', status: 'MOVING' } });
  resolveSnapshot({ epoch: 'A', revision: 0, buses: [], network_events: [] }); await flush();
  assert.equal(latest.buses.B.status, 'MOVING');
  socket.message({ type: 'resync_required' }); await flush();
  resolveSnapshot({ epoch: 'A', revision: 5, buses: [{ bus_id: 'B', status: 'STALE' }], network_events: [] }); await flush();
  assert.equal(calls, 2); assert.equal(latest.buses.B.status, 'STALE');
  stop();
});
