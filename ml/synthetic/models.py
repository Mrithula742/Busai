import torch
from torch import nn

class STBlock(nn.Module):
    def __init__(self, features, hidden):
        super().__init__()
        self.temporal=nn.Conv2d(features,hidden*2,(3,1),padding=(1,0))
        self.graph=nn.Conv2d(hidden,hidden,1)
        self.output=nn.Conv2d(hidden,hidden,(3,1),padding=(1,0))
    def forward(self,x,adjacency):
        value,gate=self.temporal(x).chunk(2,dim=1)
        x=torch.tanh(value)*torch.sigmoid(gate)
        x=torch.einsum('nm,bctm->bctn',adjacency,x)
        return torch.relu(self.output(torch.relu(self.graph(x))))

class STGCN(nn.Module):
    """Two temporal/graph/temporal blocks; 12-step input, one-step residual output."""
    def __init__(self,nodes,features=8,hidden=32):
        super().__init__()
        self.nodes,self.features=nodes,features
        self.blocks=nn.ModuleList([STBlock(features,hidden),STBlock(hidden,hidden)])
        self.head=nn.Conv2d(hidden,1,1)
    def forward(self,x,adjacency):
        if x.ndim!=4 or tuple(x.shape[1:])!=(12,self.nodes,self.features) or not torch.isfinite(x).all():
            raise ValueError('Expected finite crowd input [batch,12,nodes,8]')
        residual=x[:,-1,:,2]
        x=x.permute(0,3,1,2)
        for block in self.blocks:x=block(x,adjacency)
        return residual+self.head(x)[:,0,-1,:]
