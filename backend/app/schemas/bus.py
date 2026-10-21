from datetime import datetime
from typing import Literal, Optional
from .gps import GPSUpdate


class BusState(GPSUpdate):
    status: Literal['MOVING', 'STOPPED', 'STALE']
    received_at: datetime
    last_received_at: datetime
    stop_sequence_index: Optional[int] = None
    revision: int = 0
    route_verified: bool
    route_data_source: Literal['SAMPLE', 'GTFS', 'unavailable']
