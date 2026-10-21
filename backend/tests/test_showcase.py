import sys
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT),str(ROOT/'simulator')]
from app.main import create_app
from app.config import Settings
from app.services.forecast_service import get_bundle,forecast
from app.services.assistant_service import interpret
from app.api.synthetic import dataset
from app.services.ai_journey_service import IST
from simulator.multi_bus_simulator import SimulatedBus

NOW=datetime(2026,10,17,8,tzinfo=IST)
QUERY=dict(origin='MAD',destination='CEN',departure_time=NOW.isoformat(),max_transfers=0,preference='less_crowd')

class ShowcaseAPIs(unittest.TestCase):
    def setUp(self):
        self.ctx=TestClient(create_app(Settings(gtfs_dir=ROOT/'datasets/synthetic_chennai')));self.client=self.ctx.__enter__()
    def tearDown(self):self.ctx.__exit__(None,None,None)
    def plan(self):return self.client.post('/api/ai/journeys',json=QUERY).json()
    def preview(self,**settings):
        response=self.client.post('/api/ai/what-if',json=dict(journey=QUERY,route_id='SYN_A',**settings));self.assertEqual(response.status_code,200,response.text);return response.json()
    def test_comparison_uses_computed_factors(self):
        r=self.plan();self.assertEqual(len(r['comparison']),3)
        for card in r['comparison']:
            values=[o[{'faster':'total_minutes','less_crowd':'occupancy_ratio','most_reliable':'reliability_score'}[card['category']]] for o in r['options']]
            actual=card['option'][{'faster':'total_minutes','less_crowd':'occupancy_ratio','most_reliable':'reliability_score'}[card['category']]]
            self.assertEqual(actual,max(values) if card['category']=='most_reliable' else min(values))
    def test_what_if_changes_only_target_route_and_never_mutates_models(self):
        original=dict(forecast(8,0)['eta']);r=self.preview(traffic_factor=1.6,demand_factor=1.5,delay_minutes=10)
        before={o['route_id']:o for o in r['before']['options']};after={o['route_id']:o for o in r['after']['options']}
        self.assertGreater(after['SYN_A']['ride_minutes'],before['SYN_A']['ride_minutes'])
        self.assertGreater(after['SYN_A']['occupancy_ratio'],before['SYN_A']['occupancy_ratio'])
        self.assertLess(after['SYN_A']['reliability_score'],before['SYN_A']['reliability_score'])
        self.assertEqual(after['SYN_B'],before['SYN_B']);self.assertEqual(forecast(8,0)['eta'],original)
        self.assertEqual(self.client.get('/api/network-events').json(),[])
        self.assertEqual(self.plan()['options'],r['before']['options'])
    def test_roadblock_removes_route_and_identity_resets(self):
        self.assertNotIn('SYN_A',[o['route_id'] for o in self.preview(roadblock=True)['after']['options']])
        r=self.preview();self.assertEqual(r['before'],r['after'])
    def test_demand_decrease_is_not_a_risk_event(self):
        r=self.preview(demand_factor=.5)
        a=next(o for o in r['after']['options'] if o['route_id']=='SYN_A');b=next(o for o in r['before']['options'] if o['route_id']=='SYN_A')
        self.assertLess(a['occupancy_ratio'],b['occupancy_ratio']);self.assertEqual(a['reliability_score'],b['reliability_score'])
    def test_invalid_simulation_rejected(self):
        for changes in [dict(traffic_factor=5),dict(demand_factor=-1),dict(delay_minutes=100),dict(route_id='BAD')]:
            r=self.client.post('/api/ai/what-if',json=dict(journey=QUERY,route_id='SYN_A')|changes);self.assertEqual(r.status_code,422)
    def test_assistant_api_missing_origin_and_valid_constraints(self):
        r=self.client.post('/api/assistant/interpret',json=dict(text='Take me to Stop G with low crowd and fewer transfers.',departure_time=NOW.isoformat())).json()
        self.assertEqual(r['parser'],'RULE_BASED');self.assertEqual(r['parameters']['destination'],'KAN');self.assertEqual(r['missing_fields'],['origin'])
        r=self.client.post('/api/assistant/interpret',json=dict(text='From Madipakkam to Chennai Central at 08:00 with low crowd and fewer transfers.',departure_time=NOW.isoformat())).json()
        self.assertTrue(r['ready']);self.assertEqual(r['parameters']['secondary_preferences'],['fewer_transfers'])
        self.assertEqual(self.client.post('/api/ai/journeys',json=r['parameters']).status_code,200)
    def test_arrival_and_wait_constraints_are_enforced(self):
        r=self.client.post('/api/ai/journeys',json=QUERY|dict(arrival_deadline=NOW.replace(hour=8,minute=10).isoformat())).json();self.assertEqual(r['options'],[])
        r=self.client.post('/api/ai/journeys',json=QUERY|dict(departure_time=NOW.replace(minute=1).isoformat(),max_wait_minutes=0)).json();self.assertEqual(r['options'],[])
        self.assertEqual(self.client.post('/api/ai/journeys',json=QUERY|dict(departure_time='2026-10-17T08:00:00',arrival_deadline=NOW.replace(hour=9).isoformat())).status_code,422)
    def test_evaluation_matches_saved_metrics_and_has_real_targets(self):
        for kind in ['crowd','eta']:
            r=self.client.get('/api/models/evaluation',params=dict(model=kind));self.assertEqual(r.status_code,200,r.text);r=r.json()
            self.assertEqual(r['source'],'HELD_OUT_SYNTHETIC_EVALUATION');self.assertFalse(r['runtime_prediction'])
            m=get_bundle().meta['models'][kind]
            self.assertAlmostEqual(r['metrics']['mae'],m['test_mae'],places=5)
            self.assertAlmostEqual(r['baseline_metrics']['mae'],m['persistence_test_mae'],places=5)
            p=r['series'][0]['points'][0];b=get_bundle();raw=b.replay[kind]
            self.assertAlmostEqual(p['actual'],float(raw[28,m['history_steps'],0,m['target_index']]),places=5)
            self.assertEqual(len(r['series'][0]['points']),64)
    def put_bus(self):
        app=self.client.app
        bus=SimulatedBus(dict(bus_id='SHOWCASE',route_id='SYN_A',trip_id='SYN_A_360',speed_mps=7,start_progress=.01),app.state.gtfs,6)
        payload=bus.payload();payload['timestamp']=NOW.isoformat()
        with patch('app.services.bus_state_service.utc_now',return_value=NOW):
            self.assertEqual(self.client.post('/api/buses/location',json=payload).status_code,200)
    def test_digital_twin_sources_estimates_and_staleness(self):
        self.put_bus()
        with patch('app.api.showcase.utc_now',return_value=NOW),patch('app.services.bus_state_service.utc_now',return_value=NOW),patch('app.services.ai_journey_service.utc_now',return_value=NOW):
            r=self.client.get('/api/twin?boarding_stop=VEL');self.assertEqual(r.status_code,200,r.text);v=r.json()['vehicles'][0]
            self.assertEqual(v['source'],'SIMULATOR');self.assertEqual(v['speed_kmh'],25.2);self.assertEqual(v['tracking_status'],'FRESH');self.assertGreater(v['next_stop_eta_minutes'],0);self.assertIsNotNone(v['occupancy_ratio']);self.assertIsNotNone(v['boarding_eta_minutes'])
        with patch('app.api.showcase.utc_now',return_value=NOW+timedelta(minutes=2)),patch('app.services.bus_state_service.utc_now',return_value=NOW+timedelta(minutes=2)):
            v=self.client.get('/api/twin').json()['vehicles'][0];self.assertEqual(v['tracking_status'],'STALE');self.assertIsNone(v['next_stop_eta_minutes']);self.assertIsNone(v['occupancy_ratio'])
    def test_empty_twin_and_invalid_stop(self):
        self.assertEqual(self.client.get('/api/twin').json()['vehicles'],[])
        self.assertEqual(self.client.get('/api/twin?boarding_stop=BAD').status_code,422)

class AssistantGrammar(unittest.TestCase):
    def parse(self,text,context=NOW):return interpret(text,dataset()[1],context,now=NOW)
    def test_time_and_deadline(self):
        r=self.parse('From Stop A to Stop E after 9:30 am with low crowd');self.assertEqual(r['parameters']['departure_time'],'2026-10-17T09:30:00+05:30')
        r=self.parse('From Stop A to Stop E by 10:00');self.assertEqual(r['parameters']['arrival_deadline'],'2026-10-17T10:00:00+05:30')
    def test_unknown_and_missing_time_are_explicit(self):
        r=self.parse('Take me to Neverland',None);self.assertIn('destination',r['missing_fields']);self.assertIn('departure_time',r['missing_fields']);self.assertFalse(r['ready'])
    def test_invalid_time_and_wait_limit(self):
        self.assertFalse(self.parse('From Stop A to Stop E at 29:99')['ready'])
        self.assertFalse(self.parse('From Stop A to Stop E wait 500 minutes')['ready'])
        r=self.parse('From Stop A to Stop E direct only wait up to 10 minutes');self.assertEqual(r['parameters']['max_transfers'],0);self.assertEqual(r['parameters']['max_wait_minutes'],10)
    def test_tomorrow_and_now(self):
        self.assertTrue(self.parse('From Stop A to Stop E tomorrow at 9 am')['parameters']['departure_time'].startswith('2026-10-18T09'))
        self.assertEqual(self.parse('From Stop A to Stop E now')['parameters']['departure_time'],NOW.isoformat())
