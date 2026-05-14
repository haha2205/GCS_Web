from __future__ import annotations

import argparse
import json
import os
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import torch
from torch import Tensor

from .torch_sac import GaussianPolicy, SoftQNetwork, hard_update, mse_loss, soft_update


@dataclass
class TrainingConfig:
    input_path: str
    output_dir: str
    hidden_dims: tuple[int, ...]
    batch_size: int
    train_steps: int
    gamma: float
    tau: float
    actor_lr: float
    critic_lr: float
    alpha_lr: float
    init_alpha: float
    seed: int
    device: str
    require_confirmed_echo: bool
    drop_rollback: bool
    drop_protection_triggered: bool
    log_interval: int


def parse_args() -> TrainingConfig:
    parser = argparse.ArgumentParser(description='Train an offline PyTorch SAC model from offline_transitions.jsonl')
    parser.add_argument('--input', dest='input_path', required=True, help='Path to offline_transitions.jsonl')
    parser.add_argument('--output-dir', required=True, help='Directory used to save model artifacts')
    parser.add_argument('--hidden-dims', nargs='+', type=int, default=[256, 256], help='Hidden layer sizes for actor and critics')
    parser.add_argument('--batch-size', type=int, default=64)
    parser.add_argument('--train-steps', type=int, default=5000)
    parser.add_argument('--gamma', type=float, default=0.95)
    parser.add_argument('--tau', type=float, default=0.005)
    parser.add_argument('--actor-lr', type=float, default=3e-4)
    parser.add_argument('--critic-lr', type=float, default=3e-4)
    parser.add_argument('--alpha-lr', type=float, default=3e-4)
    parser.add_argument('--init-alpha', type=float, default=0.2)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto')
    parser.add_argument('--allow-unconfirmed-echo', action='store_true', help='Keep transitions whose parameter echo was not confirmed')
    parser.add_argument('--drop-rollback', action='store_true', help='Drop transitions that triggered rollback')
    parser.add_argument('--drop-protection-triggered', action='store_true', help='Drop transitions that hit protection logic')
    parser.add_argument('--log-interval', type=int, default=200)
    args = parser.parse_args()
    return TrainingConfig(
        input_path=args.input_path,
        output_dir=args.output_dir,
        hidden_dims=tuple(int(value) for value in args.hidden_dims),
        batch_size=int(args.batch_size),
        train_steps=int(args.train_steps),
        gamma=float(args.gamma),
        tau=float(args.tau),
        actor_lr=float(args.actor_lr),
        critic_lr=float(args.critic_lr),
        alpha_lr=float(args.alpha_lr),
        init_alpha=float(args.init_alpha),
        seed=int(args.seed),
        device=str(args.device),
        require_confirmed_echo=not bool(args.allow_unconfirmed_echo),
        drop_rollback=bool(args.drop_rollback),
        drop_protection_triggered=bool(args.drop_protection_triggered),
        log_interval=int(args.log_interval),
    )


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def resolve_device(device_name: str) -> torch.device:
    if device_name == 'cpu':
        return torch.device('cpu')
    if device_name == 'cuda':
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA was requested but is not available')
        return torch.device('cuda')
    return torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def _as_float_list(payload: Any, *, field_name: str) -> list[float]:
    if not isinstance(payload, list) or not payload:
        raise ValueError(f'{field_name} must be a non-empty list')
    values = []
    for value in payload:
        values.append(float(value))
    return values


def load_transitions(config: TrainingConfig) -> tuple[dict[str, Tensor], dict[str, Any]]:
    input_path = Path(config.input_path)
    if not input_path.exists():
        raise FileNotFoundError(f'Input file not found: {input_path}')

    states: list[list[float]] = []
    actions: list[list[float]] = []
    rewards: list[float] = []
    next_states: list[list[float]] = []
    dones: list[float] = []
    kept_records = 0
    skipped_records = 0
    experiment_groups: dict[str, int] = {}

    with input_path.open('r', encoding='utf-8') as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if config.require_confirmed_echo and not bool(payload.get('param_echo_confirmed')):
                skipped_records += 1
                continue
            if config.drop_rollback and bool(payload.get('rollback_triggered')):
                skipped_records += 1
                continue
            if config.drop_protection_triggered and bool(payload.get('protection_triggered')):
                skipped_records += 1
                continue

            try:
                state = _as_float_list(payload.get('state'), field_name=f'state at line {line_number}')
                action = _as_float_list(payload.get('action'), field_name=f'action at line {line_number}')
                next_state = _as_float_list(payload.get('next_state'), field_name=f'next_state at line {line_number}')
                reward = float(payload.get('reward'))
                done = float(bool(payload.get('done', False)))
            except (TypeError, ValueError) as exc:
                raise ValueError(f'Failed to parse transition at line {line_number}: {exc}') from exc

            if len(state) != len(next_state):
                raise ValueError(f'State dimension mismatch at line {line_number}: {len(state)} != {len(next_state)}')

            states.append(state)
            actions.append(action)
            rewards.append(reward)
            next_states.append(next_state)
            dones.append(done)
            kept_records += 1

            group_key = str(payload.get('experiment_group') or '')
            experiment_groups[group_key] = experiment_groups.get(group_key, 0) + 1

    if kept_records == 0:
        raise ValueError('No usable transitions remained after filtering')

    state_tensor = torch.tensor(states, dtype=torch.float32)
    action_tensor = torch.tensor(actions, dtype=torch.float32)
    reward_tensor = torch.tensor(rewards, dtype=torch.float32).unsqueeze(-1)
    next_state_tensor = torch.tensor(next_states, dtype=torch.float32)
    done_tensor = torch.tensor(dones, dtype=torch.float32).unsqueeze(-1)

    state_mean = state_tensor.mean(dim=0, keepdim=True)
    state_std = state_tensor.std(dim=0, keepdim=True)
    state_std = torch.where(state_std < 1e-6, torch.ones_like(state_std), state_std)

    dataset = {
        'states': (state_tensor - state_mean) / state_std,
        'actions': torch.clamp(action_tensor, min=-1.0, max=1.0),
        'rewards': reward_tensor,
        'next_states': (next_state_tensor - state_mean) / state_std,
        'dones': done_tensor,
    }
    metadata = {
        'transition_count': kept_records,
        'skipped_count': skipped_records,
        'state_dim': int(state_tensor.shape[1]),
        'action_dim': int(action_tensor.shape[1]),
        'reward_mean': float(reward_tensor.mean().item()),
        'reward_std': float(reward_tensor.std().item()),
        'action_abs_max': float(action_tensor.abs().max().item()),
        'experiment_groups': experiment_groups,
        'state_mean': state_mean.squeeze(0).tolist(),
        'state_std': state_std.squeeze(0).tolist(),
    }
    return dataset, metadata


def sample_batch(dataset: dict[str, Tensor], batch_size: int, device: torch.device) -> dict[str, Tensor]:
    data_size = dataset['states'].shape[0]
    indices = torch.randint(0, data_size, (batch_size,))
    return {key: value[indices].to(device) for key, value in dataset.items()}


def save_artifacts(
    output_dir: Path,
    config: TrainingConfig,
    actor: GaussianPolicy,
    critic1: SoftQNetwork,
    critic2: SoftQNetwork,
    metadata: dict[str, Any],
    history: list[dict[str, float]],
    alpha: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    torch.save(
        {
            'state_dict': actor.state_dict(),
            'state_dim': metadata['state_dim'],
            'action_dim': metadata['action_dim'],
            'hidden_dims': list(config.hidden_dims),
        },
        output_dir / 'actor.pt',
    )
    torch.save(
        {
            'critic1_state_dict': critic1.state_dict(),
            'critic2_state_dict': critic2.state_dict(),
            'state_dim': metadata['state_dim'],
            'action_dim': metadata['action_dim'],
            'hidden_dims': list(config.hidden_dims),
        },
        output_dir / 'critics.pt',
    )

    with (output_dir / 'state_normalizer.json').open('w', encoding='utf-8') as handle:
        json.dump(
            {
                'state_mean': metadata['state_mean'],
                'state_std': metadata['state_std'],
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )

    with (output_dir / 'training_summary.json').open('w', encoding='utf-8') as handle:
        json.dump(
            {
                'config': asdict(config),
                'data': metadata,
                'final_alpha': alpha,
                'history_tail': history[-20:],
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )


def train(config: TrainingConfig) -> None:
    set_seed(config.seed)
    device = resolve_device(config.device)
    dataset, metadata = load_transitions(config)

    actor = GaussianPolicy(metadata['state_dim'], metadata['action_dim'], config.hidden_dims).to(device)
    critic1 = SoftQNetwork(metadata['state_dim'], metadata['action_dim'], config.hidden_dims).to(device)
    critic2 = SoftQNetwork(metadata['state_dim'], metadata['action_dim'], config.hidden_dims).to(device)
    target_critic1 = SoftQNetwork(metadata['state_dim'], metadata['action_dim'], config.hidden_dims).to(device)
    target_critic2 = SoftQNetwork(metadata['state_dim'], metadata['action_dim'], config.hidden_dims).to(device)
    hard_update(target_critic1, critic1)
    hard_update(target_critic2, critic2)

    actor_optimizer = torch.optim.Adam(actor.parameters(), lr=config.actor_lr)
    critic1_optimizer = torch.optim.Adam(critic1.parameters(), lr=config.critic_lr)
    critic2_optimizer = torch.optim.Adam(critic2.parameters(), lr=config.critic_lr)
    log_alpha = torch.tensor([float(config.init_alpha)], dtype=torch.float32, device=device).log().requires_grad_(True)
    alpha_optimizer = torch.optim.Adam([log_alpha], lr=config.alpha_lr)
    target_entropy = -float(metadata['action_dim'])

    history: list[dict[str, float]] = []
    batch_size = min(config.batch_size, metadata['transition_count'])

    for step in range(1, config.train_steps + 1):
        batch = sample_batch(dataset, batch_size, device)
        alpha = log_alpha.exp()

        with torch.no_grad():
            next_policy = actor.sample(batch['next_states'])
            target_q1 = target_critic1(batch['next_states'], next_policy.action)
            target_q2 = target_critic2(batch['next_states'], next_policy.action)
            target_q = torch.min(target_q1, target_q2) - alpha * next_policy.log_prob
            td_target = batch['rewards'] + config.gamma * (1.0 - batch['dones']) * target_q

        critic1_loss = mse_loss(critic1(batch['states'], batch['actions']), td_target)
        critic2_loss = mse_loss(critic2(batch['states'], batch['actions']), td_target)

        critic1_optimizer.zero_grad(set_to_none=True)
        critic1_loss.backward()
        critic1_optimizer.step()

        critic2_optimizer.zero_grad(set_to_none=True)
        critic2_loss.backward()
        critic2_optimizer.step()

        policy_sample = actor.sample(batch['states'])
        q1_policy = critic1(batch['states'], policy_sample.action)
        q2_policy = critic2(batch['states'], policy_sample.action)
        actor_loss = (alpha.detach() * policy_sample.log_prob - torch.min(q1_policy, q2_policy)).mean()

        actor_optimizer.zero_grad(set_to_none=True)
        actor_loss.backward()
        actor_optimizer.step()

        alpha_loss = -(log_alpha * (policy_sample.log_prob + target_entropy).detach()).mean()
        alpha_optimizer.zero_grad(set_to_none=True)
        alpha_loss.backward()
        alpha_optimizer.step()

        soft_update(target_critic1, critic1, config.tau)
        soft_update(target_critic2, critic2, config.tau)

        if step == 1 or step % config.log_interval == 0 or step == config.train_steps:
            item = {
                'step': float(step),
                'actor_loss': float(actor_loss.item()),
                'critic1_loss': float(critic1_loss.item()),
                'critic2_loss': float(critic2_loss.item()),
                'alpha': float(log_alpha.exp().item()),
                'avg_log_prob': float(policy_sample.log_prob.mean().item()),
                'avg_q': float(torch.min(q1_policy, q2_policy).mean().item()),
            }
            history.append(item)
            print(json.dumps(item, ensure_ascii=False))

    save_artifacts(
        Path(config.output_dir),
        config,
        actor,
        critic1,
        critic2,
        metadata,
        history,
        float(log_alpha.exp().item()),
    )

    print(
        json.dumps(
            {
                'status': 'ok',
                'output_dir': os.path.abspath(config.output_dir),
                'transition_count': metadata['transition_count'],
                'device': str(device),
                'final_alpha': float(log_alpha.exp().item()),
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    train(parse_args())


if __name__ == '__main__':
    main()