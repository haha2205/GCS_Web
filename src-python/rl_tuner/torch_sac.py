from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch
from torch import Tensor, nn
import torch.nn.functional as F


LOG_STD_MIN = -5.0
LOG_STD_MAX = 2.0


def build_mlp(input_dim: int, hidden_dims: Sequence[int], output_dim: int) -> nn.Sequential:
    layers: list[nn.Module] = []
    current_dim = int(input_dim)
    for hidden_dim in hidden_dims:
        layers.append(nn.Linear(current_dim, int(hidden_dim)))
        layers.append(nn.ReLU())
        current_dim = int(hidden_dim)
    layers.append(nn.Linear(current_dim, int(output_dim)))
    return nn.Sequential(*layers)


@dataclass
class PolicySample:
    action: Tensor
    log_prob: Tensor
    mean_action: Tensor
    mean: Tensor
    log_std: Tensor


class GaussianPolicy(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dims: Sequence[int]) -> None:
        super().__init__()
        self.backbone = build_mlp(state_dim, hidden_dims, hidden_dims[-1])
        self.mean_head = nn.Linear(hidden_dims[-1], action_dim)
        self.log_std_head = nn.Linear(hidden_dims[-1], action_dim)

    def forward(self, states: Tensor) -> tuple[Tensor, Tensor]:
        features = self.backbone(states)
        mean = self.mean_head(features)
        log_std = self.log_std_head(features)
        log_std = torch.clamp(log_std, min=LOG_STD_MIN, max=LOG_STD_MAX)
        return mean, log_std

    def sample(self, states: Tensor) -> PolicySample:
        mean, log_std = self.forward(states)
        std = log_std.exp()
        normal = torch.distributions.Normal(mean, std)
        raw_action = normal.rsample()
        squashed_action = torch.tanh(raw_action)

        log_prob = normal.log_prob(raw_action)
        log_prob = log_prob - torch.log(1.0 - squashed_action.pow(2) + 1e-6)
        log_prob = log_prob.sum(dim=-1, keepdim=True)

        mean_action = torch.tanh(mean)
        return PolicySample(
            action=squashed_action,
            log_prob=log_prob,
            mean_action=mean_action,
            mean=mean,
            log_std=log_std,
        )

    def act(self, states: Tensor, deterministic: bool = True) -> Tensor:
        mean, _ = self.forward(states)
        if deterministic:
            return torch.tanh(mean)
        return self.sample(states).action


class SoftQNetwork(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dims: Sequence[int]) -> None:
        super().__init__()
        self.net = build_mlp(state_dim + action_dim, hidden_dims, 1)

    def forward(self, states: Tensor, actions: Tensor) -> Tensor:
        return self.net(torch.cat([states, actions], dim=-1))


def soft_update(target: nn.Module, source: nn.Module, tau: float) -> None:
    with torch.no_grad():
        for target_param, source_param in zip(target.parameters(), source.parameters()):
            target_param.data.mul_(1.0 - tau).add_(source_param.data, alpha=tau)


def hard_update(target: nn.Module, source: nn.Module) -> None:
    with torch.no_grad():
        for target_param, source_param in zip(target.parameters(), source.parameters()):
            target_param.copy_(source_param)


def mse_loss(prediction: Tensor, target: Tensor) -> Tensor:
    return F.mse_loss(prediction, target)