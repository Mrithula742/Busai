import asyncio
import anyio
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from .config import ROOT, Settings
from .api import gps, buses, stops, routes, network_events, journeys, model_demo, demo_journey
from .api import synthetic, ai, showcase
from .services.journey_service import JourneyService
from .services.bus_state_service import BusStateService
from .services.gps_service import GPSService
from .services.gtfs_service import GTFSService, load_gtfs
from .services.network_event_service import NetworkEventService
from .services.stop_progression_service import StopProgressionService
from .services.nearby_stop_service import NearbyStopService
from .websocket.manager import ConnectionManager


def create_app(settings=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        app.state.gtfs = load_gtfs(settings)
        app.state.store = BusStateService(settings.stale_seconds)
        app.state.manager = ConnectionManager()
        app.state.progression = StopProgressionService(app.state.gtfs, settings.stop_radius_meters, settings.max_stop_accuracy_meters)
        app.state.gps = GPSService(app.state.store, app.state.gtfs, app.state.manager, app.state.progression)
        app.state.events = NetworkEventService(app.state.manager, app.state.gtfs)
        app.state.nearby = NearbyStopService(app.state.gtfs, settings.walking_speed_mps)
        # Keep model replay on its trained graph while the public map uses real GTFS.
        if app.state.gtfs.data_source == 'GTFS' and any(not route.startswith(('SYN_', 'SAMPLE_')) for route in app.state.gtfs.routes):
            app.state.ai_gtfs = GTFSService(ROOT / 'datasets/synthetic_chennai')
            app.state.ai_store = BusStateService(settings.stale_seconds)
            app.state.ai_events = NetworkEventService(ConnectionManager(), app.state.ai_gtfs)
        app.state.journeys = JourneyService(app.state.gtfs, app.state.nearby, app.state.store, settings.stop_radius_meters)

        async def stale_monitor():
            while True:
                await asyncio.sleep(min(1, settings.stale_seconds / 2))
                app.state.gps.refresh_stale()
                app.state.events.expire()

        task = asyncio.create_task(stale_monitor())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title='BusSure GPS foundation', lifespan=lifespan)
    for router in (gps.router, buses.router, stops.router, routes.router, network_events.router, journeys.router, model_demo.router, demo_journey.router, synthetic.router, ai.router, showcase.router):
        app.include_router(router)

    @app.get('/api/health')
    @app.get('/health', include_in_schema=False)
    async def health():
        return {'status': 'ok', 'gtfs_loaded': app.state.gtfs.loaded, 'data_source': app.state.gtfs.data_source, 'gtfs_message': app.state.gtfs.error, 'stale_seconds': settings.stale_seconds}

    @app.get('/api/snapshot')
    async def snapshot():
        # No awaits: bus/event copies and revision form an atomic event-loop snapshot.
        app.state.gps.refresh_stale()
        app.state.events.expire()
        return {'epoch': app.state.manager.epoch, 'revision': app.state.manager.revision,
                'buses': [b.model_dump(mode='json') for b in app.state.store.list(True)],
                'network_events': [e.model_dump(mode='json') for e in app.state.events.list(True)]}

    @app.get('/gps-device')
    async def gps_device():
        return FileResponse(ROOT / 'gps_device/index.html')

    @app.websocket('/ws/buses')
    async def websocket_buses(websocket: WebSocket):
        queue = await app.state.manager.connect(websocket)
        # Subscribe first, then fetch REST snapshot; queued deltas cover the gap.
        queue.put_nowait({'type': 'ready', 'snapshot_url': '/api/snapshot', 'epoch': app.state.manager.epoch, 'revision': app.state.manager.revision})

        async def receive():
            while True:
                await websocket.receive_text()

        tasks = [asyncio.create_task(app.state.manager.send_loop(websocket, queue)), asyncio.create_task(receive())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            app.state.manager.disconnect(websocket)
            for task in tasks:
                task.cancel()
            with anyio.CancelScope(shield=True):
                await asyncio.gather(*tasks, return_exceptions=True)
                with suppress(Exception):
                    await websocket.close()

    return app


app = create_app()
