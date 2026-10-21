"""Fictional question-answer demo; never mixed into the active GTFS feed."""
import json
import re
from pathlib import Path
from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, Field
from .model_demo import historical_demo

router = APIRouter()
DATA = json.loads((Path(__file__).resolve().parents[1] / 'data/chennai_demo.json').read_text())


class DemoQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    include_model_demo: bool = False
    preference: Literal['faster', 'less_crowd', 'less_delay'] = 'faster'


@router.post('/api/demo/journey')
def answer_demo(body: DemoQuestion):
    result = dict(data_source=DATA['data_source'], warning=DATA['warning'], routes=[],
                  predicted_eta=None, predicted_crowd=None,
                  model_status='The Salvador model is not valid for these fictional Chennai routes.')
    match = re.fullmatch(r'\s*(?:i want to go\s+)?from\s+(.+?)\s+to\s+(.+?)\s*[.!?]*', body.question, re.I)
    if not match:
        return dict(result, answer='Please ask: From Madipakkam to Chennai Central. Other demo places: Velachery, Guindy, T Nagar, Chennai, Tambaram, Kanchipuram.')
    origin, destination = [s.strip().casefold() for s in match.groups()]
    for index, route in enumerate(DATA['routes']):
        stops = [s.casefold() for s in route['stops']]
        if origin in stops and destination in stops and stops.index(origin) < stops.index(destination):
            # Fixed presentation values, NOT model outputs or GPS-derived estimates.
            fast = index % 2 == 0
            ride = (24 if fast else 37) if index < 2 else (85 if fast else 105)
            wait, walk, delay = (4, 5, 8) if fast else (7, 4, 2)
            result['routes'].append(dict(route_id=route['route_id'], stops=route['stops'][stops.index(origin):stops.index(destination)+1], metrics_source='SIMULATED_DEMO', ride_minutes=ride, wait_minutes=wait, walking_minutes=walk, delay_minutes=delay, total_minutes=ride+wait+walk+delay, crowd_level='HIGH' if fast else 'LOW'))
    if result['routes']:
        key = {'faster': lambda r: r['total_minutes'], 'less_crowd': lambda r: {'LOW': 0, 'HIGH': 2}[r['crowd_level']], 'less_delay': lambda r: r['delay_minutes']}[body.preference]
        result['routes'].sort(key=lambda r: (key(r), r['total_minutes'], r['route_id']))
        winner = result['routes'][0]
        reason = {'faster': f"the shortest simulated total journey ({winner['total_minutes']} min)", 'less_crowd': f"the lowest simulated crowd ({winner['crowd_level'].lower()})", 'less_delay': f"the lowest simulated delay ({winner['delay_minutes']} min)"}[body.preference]
        result['recommended_route_id'] = winner['route_id']
        result['preference'] = body.preference
        result['answer'] = f"For this demo, I suggest {winner['route_id']} because it has {reason}. All routes and values are simulated—not live or model predictions."
    else:
        result['answer'] = 'No forward journey exists in this small fictional demo for those places. Try From Madipakkam to Chennai Central or From Chennai to Kanchipuram. This says nothing about real bus availability.'
    if body.include_model_demo:
        result['historical_model_demo'] = historical_demo()
    return result
