from pydantic import BaseModel


class NearbyStop(BaseModel):
    stop_id: str
    stop_name: str
    latitude: float
    longitude: float
    distance_meters: float
    walking_minutes: float
    estimated_walking_minutes: float
    walking_estimate: str = 'straight-line approximation'
    data_source: str
