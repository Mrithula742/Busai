import asyncio
from uuid import uuid4


class ConnectionManager:
    """Bounded per-client queues keep a slow viewer from blocking GPS ingestion."""

    def __init__(self):
        self.clients = {}
        self.epoch = str(uuid4())
        self.revision = 0

    async def connect(self, websocket):
        await websocket.accept()
        queue = asyncio.Queue(maxsize=128)
        self.clients[websocket] = queue
        return queue

    def disconnect(self, websocket):
        self.clients.pop(websocket, None)

    def publish(self, bus, event_type='BUS_LOCATION_UPDATED'):
        bus.revision = self.revision + 1
        self.publish_message(event_type, bus=bus.model_dump(mode='json'))

    def publish_message(self, event_type, **payload):
        self.revision += 1
        message = {'type': event_type, 'epoch': self.epoch, 'revision': self.revision, **payload}
        for queue in list(self.clients.values()):
            if queue.full():
                # Explicitly ask a lagging client to refresh via REST.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait({'type': 'resync_required', 'snapshot_url': '/api/snapshot', 'epoch': self.epoch})
            queue.put_nowait(message)

    async def send_loop(self, websocket, queue):
        while True:
            message = await queue.get()
            await asyncio.wait_for(websocket.send_json(message), timeout=5)
