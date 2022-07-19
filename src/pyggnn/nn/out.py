from typing import Literal, Optional, Union, Any

from torch import Tensor
import torch.nn as nn
from torch_geometric.nn import global_add_pool, global_mean_pool

from pyggnn.nn.base import Dense
from pyggnn.utils.resolve import activation_resolver


__all__ = ["Node2Property1", "Node2Property2"]


class Node2Property1(nn.Module):
    """
    The block to compute the global graph proptery from node embeddings.
    In this block, after aggregation, two more FNNs are used to deform embeddings.
    This block is used in EGNN.
    """

    def __init__(
        self,
        in_dim: int,
        hidden_dim: int = 128,
        out_dim: int = 1,
        activation: Union[Any, str] = "swish",
        aggr: Literal["add", "mean"] = "add",
        **kwargs,
    ):
        """
        Args:
            in_dim (int): number of input dim.
            hidden_dim (int, optional): number of hidden layers dim. Defaults to `128`.
            out_dim (int, optional): number of output dim. Defaults to `1`.
            activation: (str or nn.Module, optional): activation function class or name.
                Defaults to `Swish`.
            aggr (`"add"` or `"mean"`): aggregation method. Defaults to `"add"`.
        """
        super().__init__()

        act = activation_resolver(activation, **kwargs)

        aggregation = {"add": global_add_pool, "mean": global_mean_pool}
        assert aggr == "add" or aggr == "mean"
        self.aggr = aggr
        self.node_transform = nn.Sequential(
            Dense(in_dim, hidden_dim, bias=True, **kwargs),
            act,
            Dense(hidden_dim, hidden_dim, bias=True, **kwargs),
        )
        self.aggregate = aggregation[aggr]
        self.predict = nn.Sequential(
            Dense(hidden_dim, hidden_dim, bias=True, **kwargs),
            act,
            Dense(hidden_dim, out_dim, bias=False, **kwargs),
        )

        self.reset_parameters()

    def reset_parameters(self):
        for layer in self.node_transform:
            if hasattr(layer, "reset_parameters"):
                layer.reset_parameters()
        for layer in self.predict:
            if hasattr(layer, "reset_parameters"):
                layer.reset_parameters()

    def forward(self, x: Tensor, batch: Optional[Tensor] = None) -> Tensor:
        out = self.node_transform(x)
        out = self.aggregate(out, batch=batch)
        return self.predict(out)


class Node2Property2(nn.Module):
    """
    The block to compute the global graph proptery from node embeddings.
    This block contains two FNN layers and aggregation block.
    This block is used in SchNet.
    """

    def __init__(
        self,
        in_dim: int,
        hidden_dim: int = 128,
        out_dim: int = 1,
        activation: Union[Any, str] = "shifted_softplus",
        scaler: Optional[nn.Module] = None,
        aggr: Literal["add", "mean"] = "add",
        **kwargs,
    ):
        """
        Args:
            in_dim (int): number of input dim.
            hidden_dim (int, optional): number of hidden layers dim. Defaults to `128`.
            out_dim (int, optional): number of output dim. Defaults to `1`.
            activation: (str or nn.Module, optional): activation function class or name.
                Defaults to `shifted_softplus`.
            scaler: (nn.Module, optional): scaler layer. Defaults to `None`.
            aggr (`"add"` or `"mean"`): aggregation method. Defaults to `"add"`.
        """
        super().__init__()

        act = activation_resolver(activation, **kwargs)

        aggregation = {"add": global_add_pool, "mean": global_mean_pool}
        assert aggr == "add" or aggr == "mean"
        self.aggr = aggr
        self.predict = nn.Sequential(
            Dense(in_dim, hidden_dim, bias=True, **kwargs),
            act,
            Dense(hidden_dim, out_dim, bias=False, **kwargs),
        )
        self.scaler = scaler
        self.aggregate = aggregation[aggr]

        self.reset_parameters()

    def reset_parameters(self):
        for layer in self.predict:
            if hasattr(layer, "reset_parameters"):
                layer.reset_parameters()

    def forward(self, x: Tensor, batch: Optional[Tensor] = None) -> Tensor:
        out = self.predict(x)
        if self.scaler is not None:
            out = self.scaler(out)
        return self.aggregate(out, batch=batch)
