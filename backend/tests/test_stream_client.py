import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from watch_buses import StreamState


class StreamClientTests(unittest.TestCase):
    def test_snapshot_order_dedup_gap_restart(self):
        state = StreamState()
        state.reset(dict(epoch='A', revision=10, buses=[{'bus_id': 'B', 'status': 'MOVING'}], network_events=[]))
        self.assertFalse(state.apply(dict(epoch='A', revision=9, bus={'bus_id': 'B', 'status': 'MOVING'})))
        self.assertTrue(state.apply(dict(epoch='A', revision=11, bus={'bus_id': 'B', 'status': 'STALE'})))
        self.assertEqual(state.buses['B']['status'], 'STALE')
        with self.assertRaises(ValueError):
            state.apply(dict(epoch='A', revision=13))
        with self.assertRaises(ValueError):
            state.apply(dict(epoch='B', revision=1))
        state.reset(dict(epoch='B', revision=0, buses=[], network_events=[]))
        self.assertEqual(state.buses, {})
        state.apply(dict(epoch='B', revision=1, event={'event_id': 'E', 'status': 'ACTIVE'}))
        state.apply(dict(epoch='B', revision=2, event={'event_id': 'E', 'status': 'CLEARED'}))
        self.assertEqual(state.events['E']['status'], 'CLEARED')
