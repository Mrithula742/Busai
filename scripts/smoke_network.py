"""Run against a fresh sample server. PHONE_PAYLOAD_TEST is a synthetic test fixture."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    ws_url = args.backend.replace('https://', 'wss://').replace('http://', 'ws://') + '/ws/buses'
    async with httpx.AsyncClient(base_url=args.backend, timeout=5) as client:
        health = (await client.get('/api/health')).json()
        assert health['data_source'] == 'SAMPLE', health
        async with websockets.connect(ws_url) as socket:
            assert json.loads(await socket.recv())['type'] == 'ready'
            process = await asyncio.create_subprocess_exec(sys.executable, '-B', str(ROOT / 'simulator/multi_bus_simulator.py'), '--ticks', '3', '--backend', args.backend, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try:
                positions = {}
                while sum(len(points) for points in positions.values()) < 18:
                    message = json.loads(await asyncio.wait_for(socket.recv(), 10))
                    if message['type'] != 'BUS_LOCATION_UPDATED':
                        continue
                    bus = message['bus']
                    assert bus['source'] == 'SIMULATOR'
                    positions.setdefault(bus['bus_id'], []).append((bus['latitude'], bus['longitude']))
                assert len(positions) == 6, positions
                assert all(len(set(points)) == 3 for points in positions.values()), positions
                response = await client.get('/api/buses')
                assert len(response.json()) == 6, response.text
                route = await client.get('/api/routes/SAMPLE_R1/buses')
                assert len(route.json()) == 2, route.text
                assert (await client.get('/gps-device')).status_code == 200
                assert (await client.get('/api/routes/SAMPLE_R1')).status_code == 200
                nearby = await client.get('/api/stops/nearby?latitude=13&longitude=80&radius=1500&limit=2')
                assert len(nearby.json()) == 2
                # Protocol fixture only: these coordinates are NOT observed phone GPS.
                phone = dict(bus_id='PHONE_PAYLOAD_TEST', route_id='SAMPLE_R1', trip_id='SAMPLE_T1', latitude=13, longitude=80, accuracy=8, speed=None, heading=None, timestamp=datetime.now(timezone.utc).isoformat(), source='REAL_PHONE_GPS')
                response = await client.post('/api/buses/location', json=phone)
                assert response.status_code == 200, response.text
                assert json.loads(await socket.recv())['bus']['source'] == 'REAL_PHONE_GPS'
                buses = (await client.get('/api/buses')).json()
                assert len(buses) == 7 and {b['source'] for b in buses} == {'SIMULATOR', 'REAL_PHONE_GPS'}
                invalid = dict(phone, latitude=91)
                assert (await client.post('/api/buses/location', json=invalid)).status_code == 422
                network_event = dict(event_id='SMOKE_ROAD_BLOCK', event_type='ROAD_BLOCK', latitude=13, longitude=80, start_time=datetime.now(timezone.utc).isoformat(), description='Synthetic smoke test event')
                assert (await client.post('/api/network-events', json=network_event)).status_code == 201
                assert json.loads(await socket.recv())['type'] == 'NETWORK_EVENT_CREATED'
                assert len((await client.get('/api/network-events')).json()) == 1
                assert (await client.post('/api/network-events/SMOKE_ROAD_BLOCK/clear')).status_code == 200
                assert json.loads(await socket.recv())['type'] == 'NETWORK_EVENT_CLEARED'
                print('PASS: six moving buses, three routes, distinct trips, REST/WS, nearby stops, phone-payload coexistence, invalid GPS rejection, network create/clear broadcasts', flush=True)
                # Verify the real background timer and status stream, not just REST refresh.
                stale = set()
                deadline = asyncio.get_running_loop().time() + health['stale_seconds'] + 3
                while len(stale) < 7:
                    remaining = deadline - asyncio.get_running_loop().time()
                    message = json.loads(await asyncio.wait_for(socket.recv(), max(.1, remaining)))
                    if message['type'] == 'BUS_STATUS_CHANGED' and message['bus']['status'] == 'STALE':
                        stale.add(message['bus']['bus_id'])
                assert (await client.get('/api/buses')).json() == []
                assert len((await client.get('/api/buses?include_stale=true')).json()) == 7
                print('PASS: all seven test buses automatically STALE; active REST list empty', flush=True)
            finally:
                if process.returncode is None:
                    await asyncio.wait_for(process.wait(), 10)
                stdout, stderr = await process.communicate()
                if process.returncode:
                    raise RuntimeError(stderr.decode())
                print(stdout.decode())
        async with websockets.connect(ws_url) as socket:
            ready = json.loads(await socket.recv())
            snapshot = (await client.get(ready['snapshot_url'])).json()
            assert len(snapshot['buses']) == 7
            assert snapshot['network_events'][0]['status'] == 'CLEARED'
            print('PASS: reconnect snapshot includes stale buses and cleared event', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
