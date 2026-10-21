import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import create_app
from app.api.synthetic import dataset

class SyntheticTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(create_app())
    def test_split_and_bounds(self):
        _,_,model,metrics=dataset()
        self.assertEqual(metrics['training_rows'],8064)
        self.assertEqual(metrics['test_rows'],2016)
        self.assertLess(metrics['occupancy_mae_ratio'],.15)
        self.assertTrue(all(0<=value[1]<=1 and value[0]>0 for value in model.values()))
    def test_forward_reverse_and_total(self):
        for a,b in [('MAD','CEN'),('CEN','MAD')]:
            r=self.client.post('/api/synthetic/journey',json=dict(origin=a,destination=b)).json()
            self.assertEqual(len(r['routes']),2)
            for option in r['routes']:
                self.assertAlmostEqual(option['total_minutes'],option['ride_minutes']+option['wait_minutes'],places=1)
                self.assertEqual(len(option['points']),len(option['stops']))
    def test_validation(self):
        for body in [dict(origin='unknown',destination='CEN'),dict(origin='MAD',destination='MAD'),dict(origin='MAD',destination='CEN',hour=25)]:
            self.assertEqual(self.client.post('/api/synthetic/journey',json=body).status_code,422)
    def test_preferences_and_no_connection(self):
        for pref,key in [('faster','total_minutes'),('less_crowd','occupancy_ratio'),('less_delay','delay_minutes')]:
            data=self.client.post('/api/synthetic/journey',json=dict(origin='MAD',destination='CEN',preference=pref)).json()
            values=[r[key] for r in data['routes']]
            self.assertEqual(values,sorted(values))
        data=self.client.post('/api/synthetic/journey',json=dict(origin='MAD',destination='KAN')).json()
        self.assertEqual(data['routes'],[])

    def test_generated_gtfs_simulator_to_live_api(self):
        from pathlib import Path
        import sys
        from app.config import Settings, ROOT
        from app.services.gtfs_service import GTFSService
        sys.path.insert(0,str(ROOT))
        sys.path.insert(0,str(ROOT/'simulator'))
        from simulator.multi_bus_simulator import SimulatedBus
        import json
        directory=ROOT/'datasets/synthetic_chennai'
        gtfs=GTFSService(directory)
        self.assertTrue(gtfs.loaded)
        config=json.loads((directory/'simulator.json').read_text())
        with TestClient(create_app(Settings(gtfs_dir=directory))) as client:
            for bus in config['buses']:
                simulated=SimulatedBus(bus,gtfs,6)
                payload=simulated.payload()
                response=client.post('/api/buses/location',json=payload)
                self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(len(client.get('/api/buses').json()),6)
