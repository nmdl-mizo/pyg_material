from __future__ import annotations  # type: ignore

import torch
import torch.nn as nn
from torch import Tensor
from torch_sparse import SparseTensor

from pyg_material.data.datakeys import DataKeys


class BaseGNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()

    def reset_parameters(self):
        # must be implemented in child class
        return NotImplementedError

    def calc_atomic_distances(self, data_batch) -> Tensor:
        """calculate atomic distances for periodic boundary conditions.

        Args:
            data_batch (Dataloader): one batch.

        Returns:
            distance (torch.Tensor): inter atomic distances shape of (num_edge).
        """
        if data_batch.get(DataKeys.Batch) is not None:
            batch = data_batch[DataKeys.Batch]
        else:
            batch = data_batch[DataKeys.Position].new_zeros(data_batch[DataKeys.Position].shape[0], dtype=torch.long)

        edge_src, edge_dst = (
            data_batch[DataKeys.Edge_index][0],
            data_batch[DataKeys.Edge_index][1],
        )
        edge_batch = batch[edge_src]
        edge_vec = (
            data_batch[DataKeys.Position][edge_dst]
            - data_batch[DataKeys.Position][edge_src]
            # TODO: einsum can use only Double, change float
            + torch.einsum(
                "ni,nij->nj",
                data_batch[DataKeys.Edge_shift],
                data_batch[DataKeys.Lattice][edge_batch],
            )
        )
        return torch.norm(edge_vec, dim=1)

    def get_triplets(self, data_batch) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor, Tensor, Tensor]:
        """Convert edge_index to triplets.

        Args:
            data_batch (Dataloader): one batch.

        Returns:
            idx_i (Tensor): index of center atom i of shape (num_edge).
            idx_j (Tensor): index of pair atom j of shape (num_edge).
            triple_idx_i (Tensor): index of atom i of shape (num_triplets).
            triple_idx_j (Tensor): index of center atom j of shape (num_triplets).
            triple_idx_k (Tensor): index of atom k of shape (num_triplets).
            edge_idx_kj (Tensor): edge index of center k to j of shape (num_triplets).
            edge_idx_ji (Tensor): edge index of center j to i of shape (num_triplets).

        Notes:
            Indexing so that j is central.

            reference:
            https://pytorch-geometric.readthedocs.io/en/latest/_modules/torch_geometric/nn/models/dimenet.html
        """
        idx_j, idx_i = data_batch[DataKeys.Edge_index]  # j->i

        value = torch.arange(idx_j.size(0), device=idx_j.device)
        num_nodes = data_batch[DataKeys.Atom_numbers].size(0)
        adj_t = SparseTensor(
            row=idx_i,
            col=idx_j,
            value=value,
            sparse_sizes=(num_nodes, num_nodes),
        )
        adj_t_row = adj_t[idx_j]
        num_triplets = adj_t_row.set_value(None).sum(dim=1).to(torch.long)

        # Node indices (i, j, k) for triplets.
        triple_idx_i = idx_i.repeat_interleave(num_triplets)
        triple_idx_j = idx_j.repeat_interleave(num_triplets)
        triple_idx_k = adj_t_row.storage.col()
        mask = triple_idx_i != triple_idx_k  # Remove i == k triplets.
        triple_idx_i, triple_idx_j, triple_idx_k = (
            triple_idx_i[mask],
            triple_idx_j[mask],
            triple_idx_k[mask],
        )

        # Edge indices (center k -> neighbor j)
        # and (center j -> neighbor i) for triplets.
        edge_idx_kj = adj_t_row.storage.value()[mask]
        edge_idx_ji = adj_t_row.storage.row()[mask]

        return (
            idx_i,
            idx_j,
            triple_idx_i,
            triple_idx_j,
            triple_idx_k,
            edge_idx_kj,
            edge_idx_ji,
        )

    def get_data(
        self,
        data_batch,
        batch_index: bool = False,
        edge_index: bool = False,
        position: bool = False,
        atom_numbers: bool = False,
        lattice: bool = False,
        pbc: bool = False,
        edge_shift: bool = False,
        edge_attr: bool = False,
    ) -> dict[str, Tensor]:
        returns = {}
        if batch_index:
            returns[DataKeys.Batch] = data_batch[DataKeys.Batch]
        if edge_index:
            returns[DataKeys.Edge_index] = data_batch[DataKeys.Edge_index]
        if position:
            returns[DataKeys.Position] = data_batch[DataKeys.Position]
        if atom_numbers:
            returns[DataKeys.Atom_numbers] = data_batch[DataKeys.Atom_numbers]
        if lattice:
            returns[DataKeys.Lattice] = data_batch[DataKeys.Lattice]
        if pbc:
            returns[DataKeys.PBC] = data_batch[DataKeys.PBC]
        if edge_shift:
            returns[DataKeys.Edge_shift] = data_batch[DataKeys.Edge_shift]
        if edge_attr:
            returns[DataKeys.Edge_attr] = data_batch[DataKeys.Edge_attr]
        return returns