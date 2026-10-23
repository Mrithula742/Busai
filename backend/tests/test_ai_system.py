import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT),str(ROOT/'simulator')]
from app.main import create_app
from app.config import Settings
from app.api.ai import JourneyInput
from app.services.forecast_service import get_bundle,forecast,ForecastBundle
from app.services.ai_journey_service import AIJourneyService,reliability,IST
from app.services.disruption_service import impact
from app.services.bus_state_service import BusStateService
from app.services.gtfs_service import GTFSService
from app.schemas.gps import GPSUpdate
from simulator.multi_bus_simulator import SimulatedBus
from simulator.network_event_hook import active_events_for_bus,apply_network_events
from ml.synthetic.data import generate,windows
from ml.synthetic.models import STGCN
from ml.travel_time.dcrnn_v2.model import DCRNN

DATA=ROOT/'datasets/synthetic_chennai'
ASOF=datetime(2026,10,17,8,tzinfo=IST)

class Models(unittest.TestCase):
    def test_checkpoint_load_and_mapping(self):
        b=get_bundle();self.assertEqual(len(b.meta['stops']),7);self.assertEqual(len(b.meta['nodes']),18)
        f=b.predict(8,0);self.assertEqual(f['mode'],'SYNTHETIC_TRAINED_DEEP_LEARNING');self.assertEqual(len(f['crowd']),7)
        self.assertTrue(all(0<=v<=1 for v in f['crowd'].values()));self.assertTrue(all(v>0 for v in f['eta'].values()))
    def test_feature_validation(self):
        with self.assertRaises(ValueError):STGCN(7)(torch.zeros(1,12,7,7),torch.eye(7))
        x=torch.zeros(1,12,7,8);x[0,0,0,0]=float('nan')
        with self.assertRaises(ValueError):STGCN(7)(x,torch.eye(7))
    def test_dcrnn_graph_validation(self):
        with self.assertRaises(ValueError):DCRNN(18,4,16,2,2,0,4,1,np.zeros((2,9,9)))
        b=get_bundle();self.assertTrue(np.allclose(b.models['eta'].supports.sum(-1),1))
    def test_inverse_scaling_reference(self):
        b=get_bundle();info=b.meta['models']['crowd'];mean=np.asarray(info['mean'],np.float32);std=np.asarray(info['std'],np.float32)
        x=(b.replay['crowd'][34,84:96]-mean)/std
        with torch.inference_mode():raw=b.models['crowd'](torch.tensor(x[None]),b.adj).numpy()[0]
        expected=np.clip(raw*std[:,2]+mean[:,2],0,1)
        np.testing.assert_allclose(list(b.predict(8,0)['crowd'].values()),expected,atol=1e-6)
    def test_no_future_replay_leakage(self):
        b=get_bundle();before=copy.deepcopy(b.predict(8,0))
        saved=b.replay['crowd'][34,96:].copy()
        try:
            b.replay['crowd'][34,96:]=100;b.predict.cache_clear()
            self.assertEqual(before['crowd'],b.predict(8,0)['crowd'])
        finally:b.replay['crowd'][34,96:]=saved;b.predict.cache_clear()
    def test_training_only_scaler(self):
        b=get_bundle();mean=b.replay['crowd'][:21].mean(axis=(0,1))
        np.testing.assert_allclose(np.asarray(b.meta['models']['crowd']['mean'])[:,:3],mean[:,:3],atol=1e-6)
        self.assertEqual(b.meta['split'],dict(train=[0,21],validation=[21,28],test=[28,35]))
    def test_fallback_label(self):
        with patch.dict(os.environ,{'BUSSURE_DISABLE_MODELS':'1'}):f=forecast(8,0)
        self.assertEqual(f['mode'],'BASELINE_FALLBACK');self.assertIn('disabled',f['fallback_reason']);self.assertEqual(len(f['eta']),18)
    def test_corrupt_checkpoint_rejected(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)
            for p in get_bundle().directory.iterdir():
                if p.is_file():shutil.copyfile(p,dest/p.name)
            (dest/'crowd.pt').write_bytes(b'broken')
            with self.assertRaisesRegex(ValueError,'integrity'):ForecastBundle(dest)
    def test_wrong_mapping_rejected(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)
            for p in get_bundle().directory.iterdir():
                if p.is_file():shutil.copyfile(p,dest/p.name)
            meta=json.loads((dest/'manifest.json').read_text());meta['stops'].reverse();(dest/'manifest.json').write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'mapping'):ForecastBundle(dest)
    def test_generator_reproducible_and_windows(self):
        a,b=generate(),generate();np.testing.assert_array_equal(a['crowd'],b['crowd']);np.testing.assert_array_equal(a['travel'],b['travel'])
        x,y=windows(a['crowd'],12,28,35);self.assertEqual(x.shape,(1932,12,7,8));np.testing.assert_array_equal(y[0],a['crowd'][28,12,:,2])
    def test_archived_checkpoint_safe_inspection(self):
        c=torch.load(ROOT/'ml/crowd/training/results/best_stgcn_crowd_model.pt',map_location='cpu',weights_only=True)
        self.assertEqual(c['num_nodes'],10);self.assertEqual(c['in_features'],8)
        c=torch.load(ROOT/'ml/travel_time/dcrnn_v2/sunt_dev_artifacts/dcrnn_v2_best.pt',map_location='cpu',weights_only=True)
        self.assertEqual(c['model_config']['num_nodes'],9)

class Planner(unittest.TestCase):
    def setUp(self):
        self.gtfs=GTFSService(DATA);self.store=BusStateService(45);self.events=[]
    def search(self,origin='MAD',destination='CEN',**kwargs):
        body=JourneyInput(origin=origin,destination=destination,departure_time=ASOF,**kwargs)
        return AIJourneyService(self.gtfs,self.store,self.events).search(body,forecast(8,0))
    def test_direct_and_reverse(self):
        for a,b in [('MAD','CEN'),('CEN','MAD')]:
            options=self.search(a,b,max_transfers=0)['options'];self.assertEqual(len(options),2)
            for o in options:self.assertEqual(o['transfers'],0);self.assertEqual(o['legs'][0]['stop_ids'][0],a);self.assertEqual(o['legs'][0]['stop_ids'][-1],b)
    def test_transfer_buffers_and_arithmetic(self):
        result=self.search('MAD','KAN')
        self.assertGreaterEqual(len(result['options']),2)
        for o in result['options']:
            self.assertGreaterEqual(o['transfers'],1)
            for before,after in zip(o['legs'],o['legs'][1:]):self.assertGreaterEqual((datetime.fromisoformat(after['departure_time'])-datetime.fromisoformat(before['arrival_time'])).total_seconds(),300-1)
            self.assertAlmostEqual(o['total_minutes'],o['ride_minutes']+o['wait_minutes']+o['walking_minutes'],delta=.2)
            self.assertEqual(o['itinerary'][0]['type'],'WALK')
    def test_direct_only_no_impossible_transfer(self):
        self.assertEqual(self.search('MAD','KAN',max_transfers=0)['options'],[])
        body=JourneyInput(origin='MAD',destination='KAN',departure_time=ASOF.replace(hour=21,minute=59))
        self.assertEqual(AIJourneyService(self.gtfs,self.store,[]).search(body,forecast(21,59))['options'],[])
    def test_two_transfers_supported(self):
        routes=[('SYN_A','MAD','VEL',480,490),('SYN_B','VEL','GUI',500,510),('SYN_C','GUI','KAN',520,540)]
        self.gtfs.route_trips={};self.gtfs.trips={};self.gtfs.trip_stops={};self.gtfs.calendar=[];self.gtfs.calendar_dates=[]
        f=forecast(8,0);f=dict(f,eta=dict(f['eta']))
        for rid,a,b,departure,arrival in routes:
            tid=rid+'_TEST';self.gtfs.route_trips[rid]=[tid];self.gtfs.trips[tid]=dict(route_id=rid,service_id='TEST')
            self.gtfs.trip_stops[tid]=[dict(stop_id=s,arrival_time=f'{t//60:02}:{t%60:02}:00',departure_time=f'{t//60:02}:{t%60:02}:00') for s,t in [(a,departure),(b,arrival)]]
            f['eta'][(rid,a,b)]=9
        body=JourneyInput(origin='MAD',destination='KAN',departure_time=ASOF,max_transfers=2)
        result=AIJourneyService(self.gtfs,self.store,[]).search(body,f)
        self.assertEqual(len(result['options']),1);self.assertEqual(result['options'][0]['transfers'],2)
        body.max_transfers=1;self.assertEqual(AIJourneyService(self.gtfs,self.store,[]).search(body,f)['options'],[])
    def test_transfer_walk_is_included_before_buffer(self):
        # Move two independent transfer stops within walking range in a test-only graph.
        self.gtfs.stops['TNG']['latitude']=self.gtfs.stops['VEL']['latitude']+.001
        self.gtfs.stops['TNG']['longitude']=self.gtfs.stops['VEL']['longitude']
        routes=[('SYN_A','MAD','VEL',480,490),('SYN_B','TNG','KAN',505,530)]
        self.gtfs.route_trips={};self.gtfs.trips={};self.gtfs.trip_stops={};self.gtfs.calendar=[];self.gtfs.calendar_dates=[]
        f=forecast(8,0);f=dict(f,eta=dict(f['eta']))
        for rid,a,b,departure,arrival in routes:
            tid=rid+'_TEST';self.gtfs.route_trips[rid]=[tid];self.gtfs.trips[tid]=dict(route_id=rid,service_id='TEST')
            self.gtfs.trip_stops[tid]=[dict(stop_id=s,arrival_time=f'{t//60:02}:{t%60:02}:00',departure_time=f'{t//60:02}:{t%60:02}:00') for s,t in [(a,departure),(b,arrival)]];f['eta'][(rid,a,b)]=10
        body=JourneyInput(origin='MAD',destination='KAN',departure_time=ASOF,max_transfers=1)
        result=AIJourneyService(self.gtfs,self.store,[]).search(body,f)['options']
        self.assertTrue(result);self.assertTrue(any(s['type']=='TRANSFER_WALK' for s in result[0]['itinerary']))
        self.assertGreater(result[0]['walking_minutes'],1)
    def test_ranking(self):
        for pref,key,reverse in [('faster','total_minutes',False),('less_crowd','occupancy_ratio',False),('most_reliable','reliability_score',True),('fewer_transfers','transfers',False)]:
            values=[o[key] for o in self.search(preference=pref)['options']];self.assertEqual(values,sorted(values,reverse=reverse))
    def event(self,kind='CONGESTION',route='SYN_A',**kwargs):
        return dict(event_id='TEST',event_type=kind,route_id=route,severity='HIGH',latitude=12.965,longitude=80.198,start_time=ASOF-timedelta(minutes=1),end_time=ASOF+timedelta(hours=8),status='ACTIVE',**kwargs)
    def test_roadblock_alternative(self):
        self.events=[self.event('ROAD_BLOCK')];options=self.search(max_transfers=0)['options']
        self.assertEqual([o['route_id'] for o in options],['SYN_B'])
    def test_congestion_eta_and_reliability(self):
        original=next(o for o in self.search(max_transfers=0)['options'] if o['route_id']=='SYN_A')
        self.events=[self.event()];changed=next(o for o in self.search(max_transfers=0)['options'] if o['route_id']=='SYN_A')
        self.assertGreater(changed['total_minutes'],original['total_minutes']);self.assertLess(changed['reliability_score'],original['reliability_score'])
    def test_segment_scoping_and_inactive_events(self):
        self.events=[self.event('ROAD_BLOCK',segment_id='SYN_A:TNG:CEN')]
        self.assertTrue(self.search('MAD','GUI',max_transfers=0)['options'])
        self.events[0]['end_time']=ASOF-timedelta(seconds=1)
        self.assertEqual(len(self.search(max_transfers=0)['options']),2)
    def test_mid_segment_roadblock_window_is_not_missed(self):
        event=self.event('ROAD_BLOCK',segment_id='SYN_A:MAD:VEL')
        event['start_time']=ASOF+timedelta(minutes=1);event['end_time']=ASOF+timedelta(minutes=2)
        self.events=[event]
        options=self.search(max_transfers=0)['options']
        self.assertEqual([o['route_id'] for o in options],['SYN_B'])

    def test_crowd_surge_changes_ranking_input(self):
        before=next(o for o in self.search(max_transfers=0)['options'] if o['route_id']=='SYN_A')
        self.events=[self.event('CROWD_SURGE')]
        after=next(o for o in self.search(max_transfers=0)['options'] if o['route_id']=='SYN_A');self.assertGreater(after['occupancy_ratio'],before['occupancy_ratio'])
    def test_nearby_origin_and_walking(self):
        body=JourneyInput(latitude=12.9651,longitude=80.1981,destination='CEN',departure_time=ASOF)
        results=AIJourneyService(self.gtfs,self.store,[]).search(body,forecast(8,0))
        self.assertTrue(results['options']);self.assertGreater(results['options'][0]['walking_minutes'],0)
    def test_reliability_formula(self):
        score,p=reliability(10,1,5,['a'],False);self.assertEqual(score,64);self.assertEqual(sum(p.values()),36)
        self.assertEqual(reliability(100,5,2,['a','b','c','d'],False)[0],0)
    def test_live_remaining_segment_and_stale_exclusion(self):
        payload=SimulatedBus(dict(route_id='SYN_A',trip_id='SYN_A_360',bus_id='TRACK',speed_mps=7,start_progress=.01),self.gtfs,6).payload()
        payload['timestamp']=ASOF-timedelta(seconds=1)
        with patch('app.services.bus_state_service.utc_now',return_value=ASOF):self.store.update(GPSUpdate(**payload),True,'SAMPLE',0)
        with patch('app.services.ai_journey_service.utc_now',return_value=ASOF):
            result=AIJourneyService(self.gtfs,self.store,[]).live_arrival('SYN_A',tuple(['MAD','VEL','GUI','TNG','CEN']),1,forecast(8,0),480,ASOF.date())
            self.assertIsNotNone(result);self.assertGreater(result[0],480)
        with patch('app.services.ai_journey_service.utc_now',return_value=ASOF+timedelta(seconds=60)):
            self.assertIsNone(AIJourneyService(self.gtfs,self.store,[]).live_arrival('SYN_A',tuple(['MAD','VEL','GUI','TNG','CEN']),1,forecast(8,0),481,ASOF.date()))
    def test_geometry_and_heading(self):
        bus=SimulatedBus(dict(route_id='SYN_A',trip_id='SYN_A_360',bus_id='TRACK',speed_mps=7,start_progress=0),self.gtfs,6)
        self.assertGreater(len(bus.paths[0]),2);a=bus.payload();bus.advance(30);b=bus.payload();self.assertNotEqual(a['latitude'],b['latitude']);self.assertNotEqual(a['heading'],b['heading'])
        bus.advance((bus.lengths[0]-bus.offset)/bus.speed+1);self.assertGreater(bus.dwell,0);self.assertEqual(bus.payload()['speed'],0)
    def test_simulation_disruptions(self):
        config=dict(route_id='SYN_A',trip_id='SYN_A_360',bus_id='TRACK',speed_mps=7,start_progress=0)
        bus=SimulatedBus(config,self.gtfs,6);event=self.event();event['start_time']=datetime.now(timezone.utc)-timedelta(hours=1);event['end_time']=datetime.now(timezone.utc)+timedelta(hours=1)
        apply_network_events(bus,[event],10);self.assertAlmostEqual(bus.offset,70/1.6);self.assertGreater(bus.delay_seconds,0)
        event['event_type']='ROAD_BLOCK';before=bus.offset;apply_network_events(bus,[event],10);self.assertEqual(bus.offset,before);self.assertEqual(bus.payload()['speed'],0)
    def test_spatial_disruption_not_global(self):
        event=self.event();event['route_id']=None
        close=[[12.965,80.198],[12.976,80.221]];far=[[13.5,80.5],[13.6,80.6]]
        self.assertGreater(impact([event],'SYN_A',ASOF,points=close)['factor'],1)
        self.assertEqual(impact([event],'SYN_A',ASOF,points=far)['factor'],1)

class APIs(unittest.TestCase):
    def setUp(self):
        self.context=TestClient(create_app(Settings(gtfs_dir=DATA)));self.client=self.context.__enter__()
    def tearDown(self):self.context.__exit__(None,None,None)
    def test_forecast_api(self):
        eta=self.client.post('/api/predict/eta',json=dict(route_id='SYN_A')).json();self.assertEqual(len(eta['segments']),4);self.assertEqual(eta['mode'],'SYNTHETIC_TRAINED_DEEP_LEARNING')
        crowd=self.client.post('/api/predict/crowd',json=dict(stop_id='MAD')).json();self.assertEqual(len(crowd['stops']),1)
        self.assertEqual(self.client.post('/api/predict/crowd',json=dict(stop_id='bad')).status_code,422)
    def test_planner_and_invalid_inputs(self):
        body=dict(origin='MAD',destination='KAN',departure_time=ASOF.isoformat(),preference='less_crowd')
        r=self.client.post('/api/ai/journeys',json=body);self.assertEqual(r.status_code,200,r.text);self.assertTrue(r.json()['options'])
        for change in [dict(origin='bad'),dict(departure_time='2026-10-17T08:00:00'),dict(latitude=12),dict(max_transfers=3),dict(transfer_buffer=0)]:
            self.assertEqual(self.client.post('/api/ai/journeys',json={**body,**change}).status_code,422)
    def test_scenario_clear_and_insights(self):
        response=self.client.post('/api/simulation/scenarios',json=dict(route_id='SYN_A',event_type='ROAD_BLOCK'));self.assertEqual(response.status_code,201)
        eid=response.json()['event_id'];self.assertEqual(self.client.post('/api/network-events/'+eid+'/clear').status_code,200)
        self.assertEqual(self.client.get('/api/models/insights').json()['status'],'LOADED_AND_VALIDATED')
    def test_real_gtfs_coexists_with_isolated_model_demo(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            feed=Path(directory)/'gtfs'
            shutil.copytree(ROOT/'simulator/routes/sample_gtfs',feed)
            (feed/'SAMPLE').unlink(missing_ok=True)
            for file in feed.glob('*.txt'):
                file.write_text(file.read_text().replace('SAMPLE_R1','MTC_REAL_1'))
            with TestClient(create_app(Settings(gtfs_dir=feed))) as c:
                self.assertEqual(c.get('/api/transit/catalog').json()['data_source'],'GTFS')
                self.assertNotIn('MAD',c.app.state.gtfs.stops)
                body=dict(origin='MAD',destination='CEN',departure_time=ASOF.isoformat())
                response=c.post('/api/ai/journeys',json=body)
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(response.json()['data_source'],'SYNTHETIC')
                self.assertTrue(response.json()['options'])
                self.assertEqual(c.get('/api/twin').status_code,200)
                scenario=c.post('/api/simulation/scenarios',json=dict(route_id='SYN_A',event_type='ROAD_BLOCK'))
                self.assertEqual(scenario.status_code,201,scenario.text)
                self.assertEqual(c.get('/api/snapshot').json()['network_events'],[])
                self.assertEqual(len(c.app.state.ai_events.list()),1)
                self.assertEqual(c.post('/api/network-events/'+scenario.json()['event_id']+'/clear').status_code,200)
                preview=c.post('/api/ai/what-if',json=dict(journey=body,route_id='SYN_A',traffic_factor=1.2))
                self.assertEqual(preview.status_code,200,preview.text)

    def test_wrong_active_network_rejected(self):
        with patch('app.main.load_gtfs', return_value=GTFSService(ROOT/'simulator/routes/sample_gtfs',sample=True)), TestClient(create_app(Settings())) as c:
            r=c.post('/api/ai/journeys',json=dict(origin='MAD',destination='CEN',departure_time=ASOF.isoformat()));self.assertEqual(r.status_code,409)

    def test_forced_fallback_is_visible_in_api_and_insights(self):
        with patch.dict(os.environ,{'BUSSURE_DISABLE_MODELS':'1'}):
            response=self.client.post('/api/predict/eta',json={}).json()
            self.assertEqual(response['mode'],'BASELINE_FALLBACK')
            self.assertIn('disabled',response['fallback_reason'])
            self.assertEqual(self.client.get('/api/models/insights').json()['status'],'BASELINE_FALLBACK')
