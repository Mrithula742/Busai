from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, AliasChoices, computed_field, model_validator


class GPSUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)
    bus_id: str = Field(min_length=1, max_length=100)
    route_id: str = Field(min_length=1, max_length=100)
    trip_id: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed: Optional[float] = Field(default=None, ge=0, le=100, description='Metres per second; null if unavailable')
    simulation_delay_seconds: Optional[float] = Field(default=None, ge=0, description='Cumulative synthetic scenario delay; null for devices without this simulation measure')
    heading: Optional[float] = Field(default=None, ge=0, lt=360)
    accuracy_meters: Optional[float] = Field(default=None, ge=0, validation_alias=AliasChoices('accuracy_meters', 'accuracy'))
    current_stop_id: Optional[str] = None
    next_stop_id: Optional[str] = None
    timestamp: datetime
    source: Literal['REAL_PHONE_GPS', 'SIMULATOR']
    status: Literal['MOVING', 'STOPPED'] = 'MOVING'

    @model_validator(mode='before')
    @classmethod
    def compatible_accuracy_aliases(cls, values):
        if isinstance(values, dict) and 'accuracy' in values and 'accuracy_meters' in values:
            values = dict(values)
            if values.pop('accuracy') != values['accuracy_meters']:
                raise ValueError('Conflicting accuracy aliases')
        return values

    @field_validator('source', mode='before')
    @classmethod
    def legacy_source(cls, value):
        return {'real_phone': 'REAL_PHONE_GPS', 'simulated': 'SIMULATOR'}.get(value, value)

    @field_validator('status', mode='before')
    @classmethod
    def normalize_status(cls, value):
        return value.upper() if isinstance(value, str) else value

    @computed_field
    @property
    def accuracy(self) -> Optional[float]:
        return self.accuracy_meters

    @field_validator('timestamp')
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('timestamp must include timezone')
        return value
