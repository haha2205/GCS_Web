from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List

import numpy as np


class ReplayBuffer:
    def __init__(self, capacity: int = 2048) -> None:
        self._capacity = max(128, int(capacity))
        self._items: Deque[dict] = deque(maxlen=self._capacity)

    def __len__(self) -> int:
        return len(self._items)

    def append(
        self,
        state: np.ndarray,
        action: np.ndarray,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        self._items.append({
            'state': np.asarray(state, dtype=np.float64),
            'action': np.asarray(action, dtype=np.float64),
            'reward': float(reward),
            'next_state': np.asarray(next_state, dtype=np.float64),
            'done': bool(done),
        })

    def sample(self, batch_size: int) -> Dict[str, np.ndarray]:
        batch_size = min(max(1, int(batch_size)), len(self._items))
        items: List[dict] = list(self._items)
        indices = np.random.choice(len(items), size=batch_size, replace=False)
        batch = [items[int(index)] for index in indices]
        return {
            'states': np.stack([item['state'] for item in batch], axis=0),
            'actions': np.stack([item['action'] for item in batch], axis=0),
            'rewards': np.asarray([item['reward'] for item in batch], dtype=np.float64),
            'next_states': np.stack([item['next_state'] for item in batch], axis=0),
            'dones': np.asarray([item['done'] for item in batch], dtype=np.float64),
        }

    def state_dict(self) -> dict:
        return {
            'capacity': self._capacity,
            'items': [
                {
                    'state': np.asarray(item['state'], dtype=np.float64).copy(),
                    'action': np.asarray(item['action'], dtype=np.float64).copy(),
                    'reward': float(item['reward']),
                    'next_state': np.asarray(item['next_state'], dtype=np.float64).copy(),
                    'done': bool(item['done']),
                }
                for item in self._items
            ],
        }

    def load_state_dict(self, payload: dict) -> None:
        capacity = int((payload or {}).get('capacity', self._capacity) or self._capacity)
        items = list((payload or {}).get('items') or [])
        self._capacity = max(128, capacity)
        self._items = deque(maxlen=self._capacity)
        for item in items:
            self.append(
                np.asarray(item.get('state', []), dtype=np.float64),
                np.asarray(item.get('action', []), dtype=np.float64),
                float(item.get('reward', 0.0) or 0.0),
                np.asarray(item.get('next_state', []), dtype=np.float64),
                bool(item.get('done', False)),
            )