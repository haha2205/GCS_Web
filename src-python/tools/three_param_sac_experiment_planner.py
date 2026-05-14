from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RL_EXPERIMENT_ROOT = PROJECT_ROOT / 'RL_Experiments'
DEFAULT_ARCHIVE_ROOT = DEFAULT_RL_EXPERIMENT_ROOT / 'rl_tuning_batches'
DEFAULT_PARAMETER_KEYS = ['fKeVx', 'fIeVx', 'fKeAx']
DEFAULT_INITIAL_PARAMS = {'fKeVx': 2.0, 'fIeVx': 0.4, 'fKeAx': 0.55}


@dataclass
class BatchStep:
    step_id: str
    experiment_group: str
    step_type: str
    target_vx: float
    fixed_params: Dict[str, float]
    notes: str


@dataclass
class BatchPlan:
    batch_id: str
    session_id: str
    created_at: str
    archive_root: str
    task_type: str
    strategy_mode: str
    parameter_keys: List[str]
    initial_params: Dict[str, float]
    max_episodes: int
    steps: List[BatchStep]


A2_FKEVX_SCAN = [1.70, 1.85, 2.00, 2.15, 2.30]
A2_FIEVX_SCAN = [0.32, 0.36, 0.40, 0.44, 0.48]
A2_FKEAX_SCAN = [0.45, 0.50, 0.55, 0.60, 0.65]
B_TARGETS = [0.6, 0.6, 1.0, 1.0, 1.4, 1.4]


def build_default_steps() -> List[BatchStep]:
    steps: List[BatchStep] = []

    for index in range(1, 21):
        steps.append(BatchStep(
            step_id=f'A1-{index:02d}',
            experiment_group='A1',
            step_type='sac_online_episode',
            target_vx=1.0,
            fixed_params={},
            notes='SAC online convergence episode on the standard 1.0 m/s task.',
        ))

    for index, value in enumerate(A2_FKEVX_SCAN, start=1):
        steps.append(BatchStep(
            step_id=f'A2-1-{index:02d}',
            experiment_group='A2',
            step_type='manual_fixed_params',
            target_vx=1.0,
            fixed_params={'fKeVx': value, 'fIeVx': 0.40, 'fKeAx': 0.55},
            notes='Single-parameter scan for fKeVx with SAC disabled.',
        ))

    for index, value in enumerate(A2_FIEVX_SCAN, start=1):
        steps.append(BatchStep(
            step_id=f'A2-2-{index:02d}',
            experiment_group='A2',
            step_type='manual_fixed_params',
            target_vx=1.0,
            fixed_params={'fKeVx': 2.00, 'fIeVx': value, 'fKeAx': 0.55},
            notes='Single-parameter scan for fIeVx with SAC disabled.',
        ))

    for index, value in enumerate(A2_FKEAX_SCAN, start=1):
        steps.append(BatchStep(
            step_id=f'A2-3-{index:02d}',
            experiment_group='A2',
            step_type='manual_fixed_params',
            target_vx=1.0,
            fixed_params={'fKeVx': 2.00, 'fIeVx': 0.40, 'fKeAx': value},
            notes='Single-parameter scan for fKeAx with SAC disabled.',
        ))

    for index, target_vx in enumerate(B_TARGETS, start=1):
        steps.append(BatchStep(
            step_id=f'B-{index:02d}',
            experiment_group='B',
            step_type='manual_fixed_params',
            target_vx=target_vx,
            fixed_params={},
            notes='Hold the best A1 parameters or the latest safe SAC parameters; do not continue large updates.',
        ))

    return steps


def batch_dir(archive_root: Path, batch_id: str) -> Path:
    return archive_root / batch_id


def plan_path(archive_root: Path, batch_id: str) -> Path:
    return batch_dir(archive_root, batch_id) / 'plan.json'


def ledger_path(archive_root: Path, batch_id: str) -> Path:
    return batch_dir(archive_root, batch_id) / 'ledger.jsonl'


def operator_notes_path(archive_root: Path, batch_id: str) -> Path:
    return batch_dir(archive_root, batch_id) / 'operator_notes.md'


def ensure_batch_layout(archive_root: Path, batch_id: str) -> None:
    batch_root = batch_dir(archive_root, batch_id)
    batch_root.mkdir(parents=True, exist_ok=True)
    (batch_root / 'summaries').mkdir(parents=True, exist_ok=True)


def initialize_ledger(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text('', encoding='utf-8')


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + '\n')


def load_plan(path: Path) -> BatchPlan:
    payload = json.loads(path.read_text(encoding='utf-8'))
    return BatchPlan(
        batch_id=str(payload['batch_id']),
        session_id=str(payload['session_id']),
        created_at=str(payload['created_at']),
        archive_root=str(payload['archive_root']),
        task_type=str(payload['task_type']),
        strategy_mode=str(payload['strategy_mode']),
        parameter_keys=[str(item) for item in payload['parameter_keys']],
        initial_params={str(key): float(value) for key, value in payload['initial_params'].items()},
        max_episodes=int(payload['max_episodes']),
        steps=[BatchStep(
            step_id=str(item['step_id']),
            experiment_group=str(item['experiment_group']),
            step_type=str(item['step_type']),
            target_vx=float(item['target_vx']),
            fixed_params={str(key): float(value) for key, value in dict(item.get('fixed_params') or {}).items()},
            notes=str(item.get('notes') or ''),
        ) for item in payload['steps']],
    )


def write_operator_notes(archive_root: Path, plan: BatchPlan) -> None:
    notes = [
        '# Three-Parameter SAC Batch Notes',
        '',
        f'- Batch ID: {plan.batch_id}',
        f'- Session ID: {plan.session_id}',
        f'- Archive Root: {plan.archive_root}',
        '',
        '## Fixed Operator Rules',
        '',
        '- This helper only generates the batch plan and archive skeleton. It does not drive the backend API.',
        '- Each task run may require restarting the simulator or runtime environment. Treat every step as an operator-driven execution unit.',
        '- Start each episode only after parameter echo confirmation.',
        '- For `sac_online_episode`, use the backend candidate parameters and do not overwrite them manually.',
        '- For `manual_fixed_params`, apply the provided fixed parameters before executing the task.',
        '- Finish each step by writing a summary JSON file into the summaries directory and appending one ledger record.',
        '',
        '## Step Overview',
        '',
    ]
    for step in plan.steps:
        notes.append(f'- {step.step_id}: {step.experiment_group} | {step.step_type} | target_vx={step.target_vx:.2f} | fixed_params={step.fixed_params}')
    operator_notes_path(archive_root, plan.batch_id).write_text('\n'.join(notes) + '\n', encoding='utf-8')


def create_plan(args: argparse.Namespace) -> int:
    archive_root = Path(args.archive_root).resolve()
    batch_id = args.batch_id or f'three_param_sac_batch_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    ensure_batch_layout(archive_root, batch_id)
    session_id = args.session_id or batch_id
    steps = build_default_steps()
    plan = BatchPlan(
        batch_id=batch_id,
        session_id=session_id,
        created_at=datetime.now().isoformat(timespec='seconds'),
        archive_root=str(archive_root),
        task_type='velocity_tracking',
        strategy_mode='torch_sac',
        parameter_keys=list(DEFAULT_PARAMETER_KEYS),
        initial_params=dict(DEFAULT_INITIAL_PARAMS),
        max_episodes=20,
        steps=steps,
    )
    payload = {
        **asdict(plan),
        'steps': [asdict(step) for step in plan.steps],
    }
    write_json(plan_path(archive_root, batch_id), payload)
    write_operator_notes(archive_root, plan)
    initialize_ledger(ledger_path(archive_root, batch_id))
    print(f'plan_created={plan_path(archive_root, batch_id)}')
    print(f'ledger_path={ledger_path(archive_root, batch_id)}')
    return 0


def find_step(plan: BatchPlan, step_id: str) -> BatchStep:
    for step in plan.steps:
        if step.step_id == step_id:
            return step
    raise KeyError(f'Unknown step_id: {step_id}')


def command_create(args: argparse.Namespace) -> int:
    return create_plan(args)


def command_show_step(args: argparse.Namespace) -> int:
    plan = load_plan(Path(args.plan))
    step = find_step(plan, args.step_id)
    print(f"step_id={step.step_id}")
    print(f"experiment_group={step.experiment_group}")
    print(f"step_type={step.step_type}")
    print(f"target_vx={step.target_vx:.2f}")
    print('fixed_params=' + json.dumps(step.fixed_params, ensure_ascii=False, sort_keys=True))
    print(f"notes={step.notes}")
    return 0


def command_record_step(args: argparse.Namespace) -> int:
    plan = load_plan(Path(args.plan))
    step = find_step(plan, args.step_id)
    archive_root = Path(plan.archive_root)
    summary = json.loads(Path(args.summary).read_text(encoding='utf-8'))
    summary.setdefault('experiment_group', step.experiment_group)
    summary.setdefault('target_vx', step.target_vx)
    ledger_entry = {
        'event': 'step_recorded',
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'step_id': step.step_id,
        'experiment_group': step.experiment_group,
        'step_type': step.step_type,
        'target_vx': step.target_vx,
        'task_success': not args.fail,
        'summary_file': str(Path(args.summary).resolve()),
        'fixed_params': dict(step.fixed_params),
        'summary': summary,
    }
    append_jsonl(ledger_path(archive_root, plan.batch_id), {
        **ledger_entry,
    })
    print('recorded_step=' + step.step_id)
    print('ledger_path=' + str(ledger_path(archive_root, plan.batch_id)))
    return 0


def command_status(args: argparse.Namespace) -> int:
    plan = load_plan(Path(args.plan))
    ledger = ledger_path(Path(plan.archive_root), plan.batch_id)
    ledger_lines = ledger.read_text(encoding='utf-8').splitlines() if ledger.exists() else []
    print(f"batch_id={plan.batch_id}")
    print(f"session_id={plan.session_id}")
    print(f"archive_root={plan.archive_root}")
    print(f"planned_step_count={len(plan.steps)}")
    print(f"recorded_step_count={len([line for line in ledger_lines if line.strip()])}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Plan and archive helper for three-parameter Torch SAC experiments.')
    subparsers = parser.add_subparsers(dest='command', required=True)

    create_parser = subparsers.add_parser('create-plan', help='Create a batch plan and archive layout.')
    create_parser.add_argument('--batch-id', default='')
    create_parser.add_argument('--session-id', default='')
    create_parser.add_argument('--archive-root', default=str(DEFAULT_ARCHIVE_ROOT))
    create_parser.set_defaults(handler=command_create)

    show_step_parser = subparsers.add_parser('show-step', help='Show one planned step for manual execution.')
    show_step_parser.add_argument('--plan', required=True)
    show_step_parser.add_argument('--step-id', required=True)
    show_step_parser.set_defaults(handler=command_show_step)

    record_step_parser = subparsers.add_parser('record-step', help='Record one manually executed step into the ledger.')
    record_step_parser.add_argument('--plan', required=True)
    record_step_parser.add_argument('--step-id', required=True)
    record_step_parser.add_argument('--summary', required=True)
    record_step_parser.add_argument('--fail', action='store_true')
    record_step_parser.set_defaults(handler=command_record_step)

    status_parser = subparsers.add_parser('status', help='Show batch plan and ledger progress.')
    status_parser.add_argument('--plan', required=True)
    status_parser.set_defaults(handler=command_status)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == '__main__':
    sys.exit(main())
