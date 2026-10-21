"""SAMPLE GPS traffic, never official live bus locations. No ML predictions."""
import argparse
import asyncio
import json
import math
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services.gtfs_service import GTFSService
from app.utils.geo import haversine_meters
from app.utils.time_utils import utc_now
from network_event_hook import active_events_for_bus, apply_network_events


class SimulatedBus:
    def __init__(self, config, gtfs, dwell_seconds):
        self.config = config
        if not gtfs.verify(config['route_id'], config['trip_id']):
            raise ValueError('Simulator route_id/trip_id must exist in its configured GTFS')
        self.stops = [gtfs.stops[s['stop_id']] for s in gtfs.trip_stops[config['trip_id']]]
        if len(self.stops) < 2:
            raise ValueError('Simulator trips require at least two stops')
        shape=gtfs.get_trip_shape(config['trip_id'])
        self.paths=[];cursor=0
        for a,b in zip(self.stops,self.stops[1:]):
            if shape:
                start=next((i for i in range(cursor,len(shape)) if haversine_meters(*shape[i],a['latitude'],a['longitude'])<1),None)
                end=next((i for i in range((start+1) if start is not None else len(shape),len(shape)) if haversine_meters(*shape[i],b['latitude'],b['longitude'])<1),None)
                if start is None or end is None:raise ValueError('Simulator shape must contain each stop in order')
                path=shape[start:end+1];cursor=end
            else:path=[[a['latitude'],a['longitude']],[b['latitude'],b['longitude']]]
            self.paths.append(path)
        self.path_lengths=[[haversine_meters(*a,*b) for a,b in zip(path,path[1:])] for path in self.paths]
        self.lengths=[sum(parts) for parts in self.path_lengths]
        if any(length <= 0 for length in self.lengths):
            raise ValueError('Consecutive simulator stops must have distinct coordinates')
        self.speed = float(config['speed_mps'])
        progress = float(config.get('start_progress', 0))
        if not 0 <= progress < 1 or not 0 < self.speed <= 100 or not math.isfinite(dwell_seconds) or dwell_seconds < 0:
            raise ValueError('Invalid simulator speed, progress or dwell time')
        self.dwell_seconds = dwell_seconds
        self.index, self.offset, self.dwell = 0, progress * sum(self.lengths), 0
        while self.offset >= self.lengths[self.index]:
            self.offset -= self.lengths[self.index]
            self.index += 1

    def advance(self, seconds):
        while seconds > 0:
            if self.dwell > 0:
                spent = min(seconds, self.dwell)
                self.dwell -= spent
                seconds -= spent
                if self.dwell > 0:
                    break
            if self.index == len(self.stops) - 1:
                # Completed sample run: reset to first stop for the next demo cycle.
                self.index, self.offset = 0, 0
            remaining_time = (self.lengths[self.index] - self.offset) / self.speed
            if seconds < remaining_time:
                self.offset += seconds * self.speed
                break
            seconds -= remaining_time
            self.index += 1
            self.offset = 0
            self.dwell = self.dwell_seconds

    def payload(self):
        a = self.stops[self.index]
        b = self.stops[min(self.index + 1, len(self.stops) - 1)]
        if self.index<len(self.paths):
            path=self.paths[self.index];parts=self.path_lengths[self.index];left=self.offset;part=0
            while part<len(parts)-1 and left>parts[part]:left-=parts[part];part+=1
            fraction=left/parts[part] if parts[part] else 0
            p,q=path[part],path[part+1]
            lat=p[0]+fraction*(q[0]-p[0]);lon=p[1]+fraction*(q[1]-p[1])
            dy=math.radians(q[0]-p[0]);dx=math.radians(q[1]-p[1])*math.cos(math.radians(lat))
        else:lat,lon=a['latitude'],a['longitude'];dy,dx=0,0
        return {'bus_id': self.config['bus_id'], 'route_id': self.config['route_id'], 'trip_id': self.config['trip_id'], 'latitude': lat, 'longitude': lon, 'accuracy': None, 'simulation_delay_seconds': getattr(self, 'delay_seconds', 0), 'speed': 0 if self.dwell else getattr(self, 'display_speed', self.speed), 'heading': math.degrees(math.atan2(dx, dy)) % 360, 'current_stop_id': a['stop_id'], 'next_stop_id': b['stop_id'] if b != a else None, 'timestamp': utc_now().isoformat(), 'status': 'STOPPED' if self.dwell or getattr(self, 'display_speed', self.speed)==0 else 'MOVING', 'source': 'SIMULATOR'}


async def run(args):
    path = Path(args.config).resolve()
    config = json.loads(path.read_text())
    gtfs = GTFSService(path.parent / config['gtfs_directory'])
    buses = [SimulatedBus(b, gtfs, config['dwell_seconds']) for b in config['buses']]
    if not buses or len({b.config['bus_id'] for b in buses}) != len(buses):
        raise ValueError('Provide nonempty, unique bus IDs')
    interval = float(config['interval_seconds'])
    if not math.isfinite(interval) or interval <= 0 or args.ticks < 0:
        raise ValueError('interval_seconds must be positive')
    print(f'SIMULATED ONLY: {len(buses)} buses. No official live positions.', flush=True)
    async with httpx.AsyncClient(base_url=args.backend, timeout=5) as client:
        async def send(bus):
            try:
                response = await client.post('/api/buses/location', json=bus.payload())
                response.raise_for_status()
                print(f"SIMULATED {bus.config['bus_id']} {response.json()['latitude']:.6f}, {response.json()['longitude']:.6f}", flush=True)
            except httpx.HTTPError as exc:
                print(f"{bus.config['bus_id']}: {exc}; retrying next tick", file=sys.stderr, flush=True)

        previous = time.monotonic()
        ticks = 0
        while args.ticks == 0 or ticks < args.ticks:
            try:
                response = await client.get('/api/network-events')
                response.raise_for_status()
                events = response.json()
            except httpx.HTTPError as exc:
                events = []
                print(f'Network events unavailable: {exc}', file=sys.stderr, flush=True)
            now = time.monotonic()
            for bus in buses:
                apply_network_events(bus, active_events_for_bus(events, bus, utc_now()), now - previous)
            previous = now
            await asyncio.gather(*(send(bus) for bus in buses))
            ticks += 1
            if args.ticks == 0 or ticks < args.ticks:
                await asyncio.sleep(interval)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', default='http://127.0.0.1:8000')
    parser.add_argument('--config', default=str(Path(__file__).with_name('simulator_config.json')))
    parser.add_argument('--ticks', type=int, default=0, help='0 runs until Ctrl+C')
    try:
        asyncio.run(run(parser.parse_args()))
    except KeyboardInterrupt:
        print('Simulator stopped; backend will mark its buses stale.')
