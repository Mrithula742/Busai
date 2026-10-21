import { api } from './api.js';

export const emptyState = () => ({ epoch: null, revision: -1, buses: {}, events: {} });

export function fromSnapshot(snapshot) {
  return { epoch: snapshot.epoch, revision: snapshot.revision,
    buses: Object.fromEntries(snapshot.buses.map(bus => [bus.bus_id, bus])),
    events: Object.fromEntries(snapshot.network_events.map(event => [event.event_id, event])) };
}

export function applyDelta(state, message) {
  if (message.epoch !== state.epoch) throw Error('Server epoch changed');
  if (message.revision <= state.revision) return state;
  if (message.revision !== state.revision + 1) throw Error('Stream gap');
  return { ...state, revision: message.revision,
    buses: message.bus ? { ...state.buses, [message.bus.bus_id]: message.bus } : state.buses,
    events: message.event ? { ...state.events, [message.event.event_id]: message.event } : state.events };
}

export function connectLive({ onState, onStatus, snapshot = api.snapshot, Socket = WebSocket, url }) {
  let state = emptyState(), socket, stopped = false, retryTimer, delay = 1000, generation = 0;
  const address = url || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/buses`;
  function connect() {
    if (stopped) return;
    const session = ++generation;
    onStatus('connecting');
    socket = new Socket(address);
    const current = socket;
    let chain = Promise.resolve();
    async function resync() {
      onStatus('syncing');
      const data = await snapshot();
      if (stopped || session !== generation || current.readyState !== 1) return false;
      state = fromSnapshot(data); onState(state); onStatus('live'); delay = 1000;
      return true;
    }
    current.onmessage = event => {
      // Serialize deltas behind the initial REST snapshot; never lose the subscription gap.
      chain = chain.then(async () => {
        if (stopped || session !== generation) return;
        const message = JSON.parse(event.data);
        if (message.type === 'ready' || message.type === 'resync_required') { await resync(); return; }
        try { state = applyDelta(state, message); }
        catch {
          if (!await resync()) return;
          state = applyDelta(state, message);
        }
        onState(state);
      }).catch(() => { if (!stopped && session === generation) current.close(); });
    };
    current.onerror = () => current.close();
    current.onclose = () => {
      if (stopped || session !== generation) return;
      generation++; onStatus('disconnected');
      retryTimer = setTimeout(connect, delay); delay = Math.min(15000, delay * 2);
    };
  }
  connect();
  return () => { stopped = true; generation++; clearTimeout(retryTimer); socket?.close(); };
}
