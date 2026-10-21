"""Windows reference time bins; target indices never cross split boundaries."""
import torch
from torch.utils.data import Dataset


class WindowDataset(Dataset):
    def __init__(self, features, targets, observed, starts, sequence_length, horizon):
        self.features = torch.as_tensor(features, dtype=torch.float32)
        self.targets = torch.as_tensor(targets, dtype=torch.float32)
        self.observed = torch.as_tensor(observed, dtype=torch.bool)
        self.starts = starts
        self.sequence_length, self.horizon = sequence_length, horizon

    def __len__(self):
        return len(self.starts)

    def __getitem__(self, index):
        t = int(self.starts[index])
        return (self.features[t-self.sequence_length:t], self.targets[t:t+self.horizon],
                self.observed[t:t+self.horizon])
