from typing import List, Optional
from pydantic import BaseModel
from .bus import BusState
from .stop import NearbyStop


class JourneyStop(BaseModel):
    stop_id: str
    stop_name: str
    latitude: float
    longitude: float


class JourneyRoute(BaseModel):
    route_id: str
    route_short_name: str = ''
    route_long_name: str = ''


class TripSegment(BaseModel):
    trip_id: str
    boarding_index: int
    destination_index: int


class JourneyOption(BaseModel):
    option_id: str
    origin_stop: NearbyStop
    destination_stop: JourneyStop
    route: JourneyRoute
    eligible_trip_segments: List[TripSegment]
    active_buses: List[BusState]
    predicted_eta: None = None
    predicted_delay: None = None
    predicted_crowd: None = None
    reliability_score: None = None


class JourneyResults(BaseModel):
    data_source: str
    options: List[JourneyOption]
    boarding_radius_meters: float
    stale_seconds: float
    preference: Optional[str] = None
    preference_applied: bool = False
    prediction_status: str = 'Prediction model not connected yet'
    scope: str = 'Direct GTFS connectivity only; service calendar and transfers not evaluated'
    message: str = ''
