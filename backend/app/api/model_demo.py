"""Opt-in historical inference, isolated from live journey predictions."""
import csv
import json
import logging
import subprocess
import sys
from functools import lru_cache
from threading import Lock

from fastapi import APIRouter, HTTPException
from ..config import ROOT

router = APIRouter()
_lock = Lock()
ARTIFACTS = ROOT / 'ml/travel_time/dcrnn_v2/sunt_dev_artifacts'


@lru_cache(maxsize=1)
def run_demo():
    # A short-lived CPU subprocess releases model memory afterwards. The existing
    # inference CLI verifies the manifest AND saved reference predictions.
    result = subprocess.run(
        [sys.executable, '-B', '-m', 'ml.travel_time.dcrnn_v2.inference',
         '--artifacts', str(ARTIFACTS), '--sample'],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60, check=True,
    )
    data = json.loads(result.stdout)
    if data.get('saved_sample_reproduced') is not True:
        raise ValueError('Historical reference verification failed')
    with (ARTIFACTS / 'gtfs/stops.txt').open(newline='', encoding='utf-8-sig') as handle:
        names = {row['stop_id']: row['stop_name'] for row in csv.DictReader(handle)}
    return {
        'mode': 'HISTORICAL_DEMO', 'model': 'DCRNN V2',
        'dataset': 'Salvador Urban Network Transportation (Brazil)',
        'as_of': data['as_of'], 'reference_verified': True,
        'scope': data['scope'],
        'warning': 'Historical segment durations only. Not live data, a Tamil Nadu prediction, or a whole-journey ETA. Do not sum these as a journey ETA.',
        'segments': [dict(route_id=p['route_id'], from_stop_id=p['from_stop_id'],
                          to_stop_id=p['to_stop_id'], from_stop_name=names[p['from_stop_id']],
                          to_stop_name=names[p['to_stop_id']],
                          predicted_travel_time_seconds=p['predicted_travel_time_seconds'],
                          observed_input_bins=p['observed_input_bins']) for p in data['predictions']],
    }


@router.get('/api/models/historical-demo')
def historical_demo():
    # Sync endpoint runs in FastAPI's worker pool, not the GPS event loop.
    if not _lock.acquire(blocking=False):
        raise HTTPException(503, 'Model demo is busy; retry shortly', headers={'Retry-After': '3'})
    try:
        return run_demo()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        logging.getLogger(__name__).exception('Historical model demo failed')
        raise HTTPException(503, 'Historical model unavailable. Check the artifact bundle and install ml/travel_time/dcrnn_v2/requirements.txt in the backend environment.')
    finally:
        _lock.release()
