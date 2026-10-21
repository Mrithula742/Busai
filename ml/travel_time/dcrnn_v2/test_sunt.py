"""Regression tests for stop-transition extraction and bounded Parquet reads."""
from pathlib import Path
import tempfile
import unittest
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from .sunt_prepare import extract_day, selected_batches


class SUNTTests(unittest.TestCase):
    def info(self):
        return {'stops':['1','2','3'], 'all_stops':{'1','2','3','4'}, 'trip_id':'template',
                'timezone':'America/Sao_Paulo', 'stop_table':pd.DataFrame({
                    'stop_id':['1','2','3'], 'stop_lat':[-12.0,-12.001,-12.002], 'stop_lon':[-38.0]*3})}

    def rows(self, stops, seconds, ordinals=None):
        return pd.DataFrame({'vehicle':[1]*len(stops),'stop_id':stops,
                             'gps_datetime':[pd.Timestamp('2024-05-21 08:00')+pd.Timedelta(seconds=x) for x in seconds],
                             '_source_row':list(range(len(stops))) if ordinals is None else ordinals})

    def test_last_upstream_first_downstream_and_extra_stops(self):
        rows = self.rows([1,1,99,2,2,3], [0,10,20,40,50,90])
        records, counts = extract_day(rows,self.info(),'2024-05-21')
        self.assertEqual(len(records),2)
        self.assertEqual((pd.Timestamp(records[0]['arrived_at'])-pd.Timestamp(records[0]['departed_at'])).total_seconds(),30)
        self.assertEqual(records[0]['extra_non_gtfs_records'],1)
        self.assertTrue(records[0]['departed_at'].endswith('-03:00'))
        self.assertEqual(records[0]['trip_id_role'],'GTFS_topology_reference_only')

    def test_skips_discontinuities_and_long_gaps_rejected(self):
        for rows in [self.rows([1,3],[0,100]), self.rows([1,2],[0,100],[0,2]), self.rows([1,2],[0,1000])]:
            records,_=extract_day(rows,self.info(),'2024-05-21')
            self.assertEqual(records,[])

    def test_record_batch_filter_preserves_original_ordinals(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'tiny.parquet'
            pq.write_table(pa.table({'route_short_name':['1386','x','1386'], 'direction_id':['I']*3,
                                     'service_code':[12550]*3, 'vehicle':[1]*3}),path)
            frames=list(selected_batches(path,'1386','I',12550,
                ['route_short_name','direction_id','service_code','vehicle'],batch_size=2))
            self.assertEqual(pd.concat(frames)._source_row.tolist(),[0,2])


if __name__=='__main__':
    unittest.main()
