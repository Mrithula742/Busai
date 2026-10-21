import os
import math
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    gtfs_dir: Path = field(default_factory=lambda: Path(os.getenv('GTFS_DIR', str(ROOT / 'datasets/gtfs'))))
    stale_seconds: float = field(default_factory=lambda: float(os.getenv('BUS_STALE_SECONDS', '45')))
    walking_speed_mps: float = field(default_factory=lambda: float(os.getenv('WALKING_SPEED_MPS', '1.4')))
    sample_data: bool = field(default_factory=lambda: os.getenv('GTFS_SAMPLE', '0') == '1')
    stop_radius_meters: float = field(default_factory=lambda: float(os.getenv('STOP_RADIUS_METERS', '40')))
    max_stop_accuracy_meters: float = field(default_factory=lambda: float(os.getenv('MAX_STOP_ACCURACY_METERS', '100')))

    def __post_init__(self):
        values = (self.stale_seconds, self.walking_speed_mps, self.stop_radius_meters, self.max_stop_accuracy_meters)
        if any(not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError('Timeout, walking speed and stop thresholds must be finite and positive')
