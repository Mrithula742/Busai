from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class NetworkEvent(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)
    event_id: str = Field(min_length=1, max_length=100)
    event_type: Literal['ROAD_BLOCK', 'ACCIDENT', 'DIVERSION', 'CONGESTION', 'OTHER', 'BREAKDOWN', 'TEMPORARY_DELAY', 'HEAVY_RAIN', 'CROWD_SURGE']
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    route_id: Optional[str] = None
    trip_id: Optional[str] = None
    segment_id: Optional[str] = None
    severity: Optional[Literal['LOW', 'MODERATE', 'HIGH', 'CRITICAL']] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    description: str = Field(min_length=1, max_length=2000)
    status: Literal['ACTIVE', 'CLEARED'] = 'ACTIVE'



    @model_validator(mode='after')
    def check_times(self):
        for value in (self.start_time, self.end_time):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError('Event times must include a timezone')
        if self.end_time is not None and self.end_time < self.start_time:
            raise ValueError('end_time precedes start_time')
        return self
