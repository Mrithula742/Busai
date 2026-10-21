"""Explicit slower reproducibility check; does not overwrite application models."""
import json
import tempfile
import unittest
from pathlib import Path
import torch
from ml.synthetic.train import train

class Retraining(unittest.TestCase):
    def test_one_epoch_retraining_is_reproducible(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            first=train(epochs=1,output_dir=a);second=train(epochs=1,output_dir=b)
            for kind in ['eta','crowd']:
                self.assertEqual(first['models'][kind]['test_mae'],second['models'][kind]['test_mae'])
                left=torch.load(Path(a)/(kind+'.pt'),map_location='cpu',weights_only=True)
                right=torch.load(Path(b)/(kind+'.pt'),map_location='cpu',weights_only=True)
                self.assertTrue(all(torch.equal(left[k],right[k]) for k in left))
