from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class SACMetrics:
    actor_loss: float
    critic1_loss: float
    critic2_loss: float
    alpha: float
    avg_q: float
    avg_log_prob: float

    def to_dict(self) -> dict:
        return {
            'actor_loss': self.actor_loss,
            'critic1_loss': self.critic1_loss,
            'critic2_loss': self.critic2_loss,
            'alpha': self.alpha,
            'avg_q': self.avg_q,
            'avg_log_prob': self.avg_log_prob,
        }


LOG_STD_MIN = -5.0
LOG_STD_MAX = 1.0


class _ActorNetwork(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dim1: int = 64, hidden_dim2: int = 64) -> None:
        super().__init__()
        self.backbone = nn.Sequential(
            nn.Linear(state_dim, hidden_dim1),
            nn.ReLU(),
            nn.Linear(hidden_dim1, hidden_dim2),
            nn.ReLU(),
        )
        self.mean_head = nn.Linear(hidden_dim2, action_dim)
        self.log_std_head = nn.Linear(hidden_dim2, action_dim)

    def forward(self, states: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        hidden = self.backbone(states)
        mean = self.mean_head(hidden)
        log_std = torch.clamp(self.log_std_head(hidden), min=LOG_STD_MIN, max=LOG_STD_MAX)
        return mean, log_std


class _CriticNetwork(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dim1: int = 64, hidden_dim2: int = 64) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim1),
            nn.ReLU(),
            nn.Linear(hidden_dim1, hidden_dim2),
            nn.ReLU(),
            nn.Linear(hidden_dim2, 1),
        )

    def forward(self, states: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat([states, actions], dim=-1)).squeeze(-1)


class LightweightSACAgent:
    def __init__(
        self,
        *,
        state_dim: int,
        action_dim: int,
        gamma: float = 0.95,
        tau: float = 0.05,
        actor_lr: float = 0.01,
        critic_lr: float = 0.02,
        alpha_lr: float = 0.01,
        init_alpha: float = 0.2,
        batch_size: int = 16,
        seed: int = 42,
    ) -> None:
        self.state_dim = int(state_dim)
        self.action_dim = int(action_dim)
        self.gamma = float(gamma)
        self.tau = float(tau)
        self.actor_lr = float(actor_lr)
        self.critic_lr = float(critic_lr)
        self.alpha_lr = float(alpha_lr)
        self.alpha = float(init_alpha)
        self.batch_size = int(batch_size)
        self.target_entropy = -float(action_dim)
        self.rng = np.random.default_rng(seed)

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.actor = _ActorNetwork(self.state_dim, self.action_dim).to(self.device)
        self.q1 = _CriticNetwork(self.state_dim, self.action_dim).to(self.device)
        self.q2 = _CriticNetwork(self.state_dim, self.action_dim).to(self.device)
        self.target_q1 = _CriticNetwork(self.state_dim, self.action_dim).to(self.device)
        self.target_q2 = _CriticNetwork(self.state_dim, self.action_dim).to(self.device)
        self.target_q1.load_state_dict(self.q1.state_dict())
        self.target_q2.load_state_dict(self.q2.state_dict())
        self.target_q1.eval()
        self.target_q2.eval()

        self.actor_optimizer = torch.optim.Adam(self.actor.parameters(), lr=self.actor_lr)
        self.q1_optimizer = torch.optim.Adam(self.q1.parameters(), lr=self.critic_lr)
        self.q2_optimizer = torch.optim.Adam(self.q2.parameters(), lr=self.critic_lr)
        self.log_alpha = torch.tensor(np.log(max(self.alpha, 1e-6)), dtype=torch.float32, device=self.device, requires_grad=True)
        self.alpha_optimizer = torch.optim.Adam([self.log_alpha], lr=self.alpha_lr)

    def _to_tensor(self, array: np.ndarray) -> torch.Tensor:
        return torch.as_tensor(array, dtype=torch.float32, device=self.device)

    def _sample_policy(self, states: torch.Tensor, deterministic: bool = False) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        mean, log_std = self.actor(states)
        std = log_std.exp()
        if deterministic:
            raw_action = mean
        else:
            raw_action = torch.distributions.Normal(mean, std).rsample()
        action = torch.tanh(raw_action)

        normal = torch.distributions.Normal(mean, std)
        log_prob = normal.log_prob(raw_action).sum(dim=-1)
        log_prob -= torch.log(1.0 - action.pow(2) + 1e-6).sum(dim=-1)
        return action, log_prob, mean, std

    def select_action(self, state: np.ndarray, deterministic: bool = False) -> Tuple[np.ndarray, dict]:
        state_array = np.asarray(state, dtype=np.float32)
        state_tensor = self._to_tensor(state_array[None, :])
        self.actor.eval()
        with torch.no_grad():
            action, log_prob, mean, std = self._sample_policy(state_tensor, deterministic=deterministic)
        self.actor.train()
        return action.squeeze(0).detach().cpu().numpy().astype(np.float64), {
            'mean': torch.tanh(mean).squeeze(0).detach().cpu().tolist(),
            'std': std.squeeze(0).detach().cpu().tolist(),
            'log_prob': float(log_prob.item()),
        }

    def update(self, replay_buffer) -> Dict[str, float] | None:
        if len(replay_buffer) < self.batch_size:
            return None

        batch = replay_buffer.sample(self.batch_size)
        states = self._to_tensor(np.asarray(batch['states'], dtype=np.float32))
        actions = self._to_tensor(np.asarray(batch['actions'], dtype=np.float32))
        rewards = self._to_tensor(np.asarray(batch['rewards'], dtype=np.float32))
        next_states = self._to_tensor(np.asarray(batch['next_states'], dtype=np.float32))
        dones = self._to_tensor(np.asarray(batch['dones'], dtype=np.float32))

        alpha = self.log_alpha.exp()

        with torch.no_grad():
            next_actions, next_log_probs, _, _ = self._sample_policy(next_states, deterministic=False)
            target_q1 = self.target_q1(next_states, next_actions)
            target_q2 = self.target_q2(next_states, next_actions)
            target_q = torch.minimum(target_q1, target_q2) - alpha * next_log_probs
            td_target = rewards + self.gamma * (1.0 - dones) * target_q

        q1_pred = self.q1(states, actions)
        q2_pred = self.q2(states, actions)
        critic1_loss_tensor = F.mse_loss(q1_pred, td_target)
        critic2_loss_tensor = F.mse_loss(q2_pred, td_target)

        self.q1_optimizer.zero_grad(set_to_none=True)
        critic1_loss_tensor.backward()
        self.q1_optimizer.step()

        self.q2_optimizer.zero_grad(set_to_none=True)
        critic2_loss_tensor.backward()
        self.q2_optimizer.step()

        policy_actions, log_probs, policy_mean, policy_std = self._sample_policy(states, deterministic=False)
        q1_policy = self.q1(states, policy_actions)
        q2_policy = self.q2(states, policy_actions)
        q_min = torch.minimum(q1_policy, q2_policy)
        actor_loss_tensor = (alpha.detach() * log_probs - q_min).mean()

        self.actor_optimizer.zero_grad(set_to_none=True)
        actor_loss_tensor.backward()
        self.actor_optimizer.step()

        alpha_loss_tensor = -(self.log_alpha * (log_probs.detach() + self.target_entropy)).mean()
        self.alpha_optimizer.zero_grad(set_to_none=True)
        alpha_loss_tensor.backward()
        self.alpha_optimizer.step()
        self.alpha = float(self.log_alpha.exp().detach().cpu().item())

        self._soft_update(self.target_q1, self.q1)
        self._soft_update(self.target_q2, self.q2)

        metrics = SACMetrics(
            actor_loss=float(actor_loss_tensor.detach().cpu().item()),
            critic1_loss=float(critic1_loss_tensor.detach().cpu().item()),
            critic2_loss=float(critic2_loss_tensor.detach().cpu().item()),
            alpha=self.alpha,
            avg_q=float(q_min.detach().mean().cpu().item()),
            avg_log_prob=float(log_probs.detach().mean().cpu().item()),
        )
        return metrics.to_dict()

    def _soft_update(self, target: nn.Module, source: nn.Module) -> None:
        for target_param, source_param in zip(target.parameters(), source.parameters()):
            target_param.data.mul_(1.0 - self.tau).add_(self.tau * source_param.data)

    def state_dict(self) -> Dict[str, Any]:
        return {
            'actor': self.actor.state_dict(),
            'q1': self.q1.state_dict(),
            'q2': self.q2.state_dict(),
            'target_q1': self.target_q1.state_dict(),
            'target_q2': self.target_q2.state_dict(),
            'actor_optimizer': self.actor_optimizer.state_dict(),
            'q1_optimizer': self.q1_optimizer.state_dict(),
            'q2_optimizer': self.q2_optimizer.state_dict(),
            'alpha_optimizer': self.alpha_optimizer.state_dict(),
            'log_alpha': self.log_alpha.detach().cpu(),
            'metadata': {
                'state_dim': self.state_dim,
                'action_dim': self.action_dim,
                'gamma': self.gamma,
                'tau': self.tau,
                'actor_lr': self.actor_lr,
                'critic_lr': self.critic_lr,
                'alpha_lr': self.alpha_lr,
                'batch_size': self.batch_size,
                'target_entropy': self.target_entropy,
            },
        }

    def load_state_dict(self, checkpoint: Dict[str, Any]) -> None:
        self.actor.load_state_dict(checkpoint['actor'])
        self.q1.load_state_dict(checkpoint['q1'])
        self.q2.load_state_dict(checkpoint['q2'])
        self.target_q1.load_state_dict(checkpoint['target_q1'])
        self.target_q2.load_state_dict(checkpoint['target_q2'])
        self.actor_optimizer.load_state_dict(checkpoint['actor_optimizer'])
        self.q1_optimizer.load_state_dict(checkpoint['q1_optimizer'])
        self.q2_optimizer.load_state_dict(checkpoint['q2_optimizer'])
        self.alpha_optimizer.load_state_dict(checkpoint['alpha_optimizer'])
        log_alpha = checkpoint.get('log_alpha')
        if log_alpha is not None:
            self.log_alpha = torch.as_tensor(log_alpha, dtype=torch.float32, device=self.device).clone().detach().requires_grad_(True)
            self.alpha_optimizer = torch.optim.Adam([self.log_alpha], lr=self.alpha_lr)
            if checkpoint.get('alpha_optimizer'):
                self.alpha_optimizer.load_state_dict(checkpoint['alpha_optimizer'])
        self.alpha = float(self.log_alpha.exp().detach().cpu().item())

NeuralSACAgent = LightweightSACAgent
