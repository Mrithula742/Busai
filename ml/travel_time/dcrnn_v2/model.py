"""New DCRNN architecture: dual random-walk diffusion, DCGRU encoder/decoder.

This architecture has no compatibility claim with the archived V1 model.
"""
import torch
from torch import nn


class DiffusionConv(nn.Module):
    def __init__(self, input_dim, output_dim, diffusion_steps):
        super().__init__()
        self.diffusion_steps = diffusion_steps
        self.linear = nn.Linear(input_dim * (1 + 2 * diffusion_steps), output_dim)

    def forward(self, x, supports):
        # x: B,N,C. Each support row lists the neighbors aggregated into that node.
        terms = [x]
        for support in supports:
            propagated = x
            for _ in range(self.diffusion_steps):
                propagated = torch.einsum('nm,bmc->bnc', support, propagated)
                terms.append(propagated)
        return self.linear(torch.cat(terms, dim=-1))


class DCGRUCell(nn.Module):
    def __init__(self, input_dim, hidden_dim, diffusion_steps):
        super().__init__()
        self.gates = DiffusionConv(input_dim + hidden_dim, 2 * hidden_dim, diffusion_steps)
        self.candidate = DiffusionConv(input_dim + hidden_dim, hidden_dim, diffusion_steps)

    def forward(self, x, hidden, supports):
        reset, update = torch.sigmoid(self.gates(torch.cat([x, hidden], -1), supports)).chunk(2, -1)
        candidate = torch.tanh(self.candidate(torch.cat([x, reset * hidden], -1), supports))
        return update * hidden + (1 - update) * candidate


class DCRNN(nn.Module):
    def __init__(self, num_nodes, input_dim, hidden_dim, num_layers, diffusion_steps,
                 dropout, sequence_length, prediction_horizon, supports):
        super().__init__()
        if min(num_nodes, input_dim, hidden_dim, num_layers, diffusion_steps,
               sequence_length, prediction_horizon) < 1 or not 0 <= dropout < 1:
            raise ValueError('Invalid DCRNN dimensions or dropout')
        supports = torch.as_tensor(supports, dtype=torch.float32)
        if supports.shape != (2, num_nodes, num_nodes) or not torch.isfinite(supports).all():
            raise ValueError(f'Supports must have finite shape (2, {num_nodes}, {num_nodes})')
        if (supports < 0).any() or not torch.allclose(supports.sum(-1), torch.ones(2, num_nodes), atol=1e-5):
            raise ValueError('Supports must be nonnegative row-normalized random walks')
        self.register_buffer('supports', supports.clone())
        self.num_nodes, self.input_dim, self.hidden_dim = num_nodes, input_dim, hidden_dim
        self.sequence_length, self.prediction_horizon = sequence_length, prediction_horizon
        self.encoder = nn.ModuleList([
            DCGRUCell(input_dim if i == 0 else hidden_dim, hidden_dim, diffusion_steps)
            for i in range(num_layers)])
        self.decoder = nn.ModuleList([
            DCGRUCell(1 if i == 0 else hidden_dim, hidden_dim, diffusion_steps)
            for i in range(num_layers)])
        self.output = nn.Linear(hidden_dim, 1)
        self.dropout = nn.Dropout(dropout)

    def _step(self, x, states, cells):
        next_states = []
        for i, cell in enumerate(cells):
            hidden = cell(x, states[i], self.supports)
            next_states.append(hidden)
            x = self.dropout(hidden) if i < len(cells) - 1 else hidden
        return next_states

    def forward(self, x):
        expected = (self.sequence_length, self.num_nodes, self.input_dim)
        if x.ndim != 4 or tuple(x.shape[1:]) != expected:
            raise ValueError(f'Expected input (batch, {self.sequence_length}, {self.num_nodes}, {self.input_dim}), got {tuple(x.shape)}')
        if not torch.isfinite(x).all():
            raise ValueError('Model input contains NaN or infinity')
        states = [x.new_zeros(x.shape[0], self.num_nodes, self.hidden_dim) for _ in self.encoder]
        for step in x.unbind(1):
            states = self._step(step, states, self.encoder)
        decoder_input = x[:, -1, :, :1]  # last standardized travel-time observation
        predictions = []
        for _ in range(self.prediction_horizon):
            states = self._step(decoder_input, states, self.decoder)
            decoder_input = self.output(states[-1])
            predictions.append(decoder_input.squeeze(-1))
        return torch.stack(predictions, dim=1)
