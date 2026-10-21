import asyncio
import json
import sys
import httpx
import websockets


class StreamState:
    """Atomic snapshot baseline plus ordered deltas; stale transitions need revisions."""
    def __init__(self):
        self.epoch, self.revision = None, -1
        self.buses, self.events = {}, {}

    def reset(self, snapshot):
        self.epoch, self.revision = snapshot['epoch'], snapshot['revision']
        self.buses = {b['bus_id']: b for b in snapshot['buses']}
        self.events = {e['event_id']: e for e in snapshot['network_events']}

    def apply(self, message):
        if message['epoch'] != self.epoch:
            raise ValueError('Server restarted; resync required')
        if message['revision'] <= self.revision:
            return False
        if message['revision'] != self.revision + 1:
            raise ValueError('Stream gap; resync required')
        if 'bus' in message:
            self.buses[message['bus']['bus_id']] = message['bus']
        if 'event' in message:
            self.events[message['event']['event_id']] = message['event']
        self.revision = message['revision']
        return True


async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else 'ws://127.0.0.1:8000/ws/buses'
    base = url.replace('wss://', 'https://', 1).replace('ws://', 'http://', 1).split('/ws/buses')[0]
    state = StreamState()
    delay = 1
    async with httpx.AsyncClient(base_url=base, timeout=10) as client:
        async def resync():
            response = await client.get('/api/snapshot')
            response.raise_for_status()
            state.reset(response.json())
            print(f'SNAPSHOT: {len(state.buses)} buses, {len(state.events)} events, revision {state.revision}', flush=True)

        while True:
            try:
                async with websockets.connect(url, open_timeout=10) as socket:
                    # Socket is subscribed before fetching snapshot; queued messages bridge the gap.
                    async for raw in socket:
                        message = json.loads(raw)
                        if message['type'] in ('ready', 'resync_required'):
                            await resync()
                            delay = 1
                            continue
                        try:
                            applied = state.apply(message)
                        except ValueError:
                            await resync()
                            applied = state.apply(message)
                        if applied:
                            print(raw, flush=True)
            except (OSError, httpx.HTTPError, websockets.exceptions.WebSocketException, ValueError) as exc:
                print(f'Disconnected: {exc}; reconnecting in {delay}s', flush=True)
            await asyncio.sleep(delay)
            delay = min(15, delay * 2)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
