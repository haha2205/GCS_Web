from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, Optional


class CmdIdx(IntEnum):
    CMD_NONE = 0
    CMD_EXTERNAL_CONTROL = 1
    CMD_MIXED_CONTROL = 2
    CMD_PROGRAM_CONTROL = 3
    CMD_CLIMB = 4
    CMD_CRUISE = 5
    CMD_DESCENT = 6
    CMD_DISABLE_ALT_HOLD = 7
    CMD_HEADING_HOLD = 8
    CMD_LEFT_CIRCLE = 9
    CMD_RIGHT_CIRCLE = 10
    CMD_HEADING_LOCK = 11
    CMD_ENGINE_START = 12
    CMD_ENGINE_STOP = 13
    CMD_AUTO_TAKEOFF = 14
    CMD_AUTO_LAND = 15
    CMD_HOVER = 16
    CMD_RETURN_TO_HOME = 17
    CMD_PRE_CONTROL = 18
    CMD_GROUND_SPEED = 19
    CMD_AIR_SPEED = 20
    CMD_TAKEOFF_PREP = 21
    CMD_MANUAL_TAKEOFF = 22
    CMD_MANUAL_LAND = 23
    CMD_PLAN_ON = 24
    CMD_PLAN_OFF = 25


@dataclass(frozen=True)
class MissionTaskDefinition:
    cmd_id: int
    task_code: str
    display_name: str
    task_group: str
    mission_phase: str
    planning_related: bool
    description: str


TASK_REGISTRY: Dict[int, MissionTaskDefinition] = {
    0: MissionTaskDefinition(0, 'idle', 'Idle', 'idle', 'idle', False, 'No active flight task.'),
    1: MissionTaskDefinition(1, 'external_control', 'External Control', 'manual_control', 'manual', False, 'Ground operator directly controls the aircraft.'),
    2: MissionTaskDefinition(2, 'mixed_control', 'Mixed Control', 'hybrid_control', 'manual', False, 'Manual and onboard control are mixed.'),
    3: MissionTaskDefinition(3, 'program_control', 'Program Control', 'program_control', 'guided', False, 'Programmed control mode without planning enable.'),
    4: MissionTaskDefinition(4, 'climb', 'Climb', 'transition', 'climb', False, 'Aircraft enters climb transition.'),
    5: MissionTaskDefinition(5, 'cruise', 'Cruise', 'nominal_mission', 'cruise', False, 'Nominal forward cruise flight.'),
    6: MissionTaskDefinition(6, 'descent', 'Descent', 'transition', 'descent', False, 'Aircraft enters descent transition.'),
    7: MissionTaskDefinition(7, 'disable_alt_hold', 'Disable Alt Hold', 'manual_control', 'manual', False, 'Altitude hold is disabled.'),
    8: MissionTaskDefinition(8, 'heading_hold', 'Heading Hold', 'stability_control', 'hold', False, 'Heading hold mode is active.'),
    9: MissionTaskDefinition(9, 'left_circle', 'Left Circle', 'maneuver', 'maneuver', False, 'Aircraft performs a left loiter or circle maneuver.'),
    10: MissionTaskDefinition(10, 'right_circle', 'Right Circle', 'maneuver', 'maneuver', False, 'Aircraft performs a right loiter or circle maneuver.'),
    11: MissionTaskDefinition(11, 'heading_lock', 'Heading Lock', 'stability_control', 'hold', False, 'Heading lock mode is active.'),
    12: MissionTaskDefinition(12, 'engine_start', 'Engine Start', 'ground_operation', 'startup', False, 'Propulsion startup on ground.'),
    13: MissionTaskDefinition(13, 'engine_stop', 'Engine Stop', 'ground_operation', 'shutdown', False, 'Propulsion shutdown on ground.'),
    14: MissionTaskDefinition(14, 'auto_takeoff', 'Auto Takeoff', 'takeoff', 'takeoff', False, 'Automatic takeoff profile.'),
    15: MissionTaskDefinition(15, 'auto_land', 'Auto Land', 'landing', 'landing', False, 'Automatic landing profile.'),
    16: MissionTaskDefinition(16, 'hover', 'Hover', 'nominal_mission', 'hover', False, 'Hover stabilization phase.'),
    17: MissionTaskDefinition(17, 'return_to_home', 'Return To Home', 'recovery', 'return_home', True, 'Recovery or emergency return mission.'),
    18: MissionTaskDefinition(18, 'pre_control', 'Pre Control', 'ground_operation', 'pre_control', False, 'Pre-control before takeoff or mode transition.'),
    19: MissionTaskDefinition(19, 'ground_speed', 'Ground Speed', 'speed_control', 'speed_control', False, 'Ground speed control mode.'),
    20: MissionTaskDefinition(20, 'air_speed', 'Air Speed', 'speed_control', 'speed_control', False, 'Air speed control mode.'),
    21: MissionTaskDefinition(21, 'takeoff_prep', 'Takeoff Prep', 'takeoff', 'takeoff_prep', False, 'Preparation stage before takeoff.'),
    22: MissionTaskDefinition(22, 'manual_takeoff', 'Manual Takeoff', 'takeoff', 'manual_takeoff', False, 'Manual takeoff profile.'),
    23: MissionTaskDefinition(23, 'manual_land', 'Manual Land', 'landing', 'manual_landing', False, 'Manual landing profile.'),
    24: MissionTaskDefinition(24, 'plan_on', 'Plan On', 'planning_mission', 'avoidance', True, 'Planning and avoidance are enabled.'),
    25: MissionTaskDefinition(25, 'plan_off', 'Plan Off', 'planning_mission', 'direct_control', False, 'Planning and avoidance are disabled.'),
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def extract_cmd_id(payload: Dict[str, Any]) -> int:
    return _safe_int(payload.get('Tele_GCS_CmdIdx', payload.get('CmdIdx', 0)), 0)


def extract_mission_id(payload: Dict[str, Any]) -> int:
    return _safe_int(payload.get('Tele_GCS_Mission', payload.get('Mission', payload.get('CmdMission', 0))), 0)


def get_task_definition(cmd_id: int) -> MissionTaskDefinition:
    return TASK_REGISTRY.get(cmd_id, MissionTaskDefinition(cmd_id, f'cmd_{cmd_id}', f'Cmd {cmd_id}', 'unknown', 'unknown', False, 'Undefined command id.'))


@dataclass
class TaskSnapshot:
    desired_cmd_id: int
    confirmed_cmd_id: int
    effective_cmd_id: int
    mission_id: int
    task_code: str
    display_name: str
    task_group: str
    mission_phase: str
    planning_related: bool
    stable_samples: int
    source: str


class FlightTaskTracker:
    """Resolve the current flight task from GCS command intent and FCS feedback."""

    def __init__(self, confirm_threshold: int = 3):
        self.confirm_threshold = confirm_threshold
        self.last_desired_cmd_id = 0
        self.last_confirmed_cmd_id = 0
        self.effective_cmd_id = 0
        self.last_mission_id = 0
        self._candidate_cmd_id = 0
        self._candidate_count = 0

    def update(
        self,
        *,
        gcs_payload: Optional[Dict[str, Any]] = None,
        telemetry_payload: Optional[Dict[str, Any]] = None,
    ) -> TaskSnapshot:
        if gcs_payload is not None:
            self.last_desired_cmd_id = extract_cmd_id(gcs_payload)
            self.last_mission_id = extract_mission_id(gcs_payload) or self.last_mission_id

        if telemetry_payload is not None:
            self.last_confirmed_cmd_id = extract_cmd_id(telemetry_payload)
            telemetry_mission = extract_mission_id(telemetry_payload)
            if telemetry_mission:
                self.last_mission_id = telemetry_mission
            self._update_effective_cmd(self.last_confirmed_cmd_id)
        elif gcs_payload is not None and self.effective_cmd_id == 0:
            self._update_effective_cmd(self.last_desired_cmd_id)

        task = get_task_definition(self.effective_cmd_id)
        source = 'telemetry_confirmed' if self.last_confirmed_cmd_id == self.effective_cmd_id else 'gcs_intent'
        return TaskSnapshot(
            desired_cmd_id=self.last_desired_cmd_id,
            confirmed_cmd_id=self.last_confirmed_cmd_id,
            effective_cmd_id=self.effective_cmd_id,
            mission_id=self.last_mission_id,
            task_code=task.task_code,
            display_name=task.display_name,
            task_group=task.task_group,
            mission_phase=task.mission_phase,
            planning_related=task.planning_related,
            stable_samples=self._candidate_count,
            source=source,
        )

    def _update_effective_cmd(self, cmd_id: int) -> None:
        cmd_id = _safe_int(cmd_id, 0)
        if cmd_id == self._candidate_cmd_id:
            self._candidate_count += 1
        else:
            self._candidate_cmd_id = cmd_id
            self._candidate_count = 1

        if self._candidate_count >= self.confirm_threshold or self.effective_cmd_id == 0:
            self.effective_cmd_id = self._candidate_cmd_id


def build_task_snapshot(message_type: str, payload: Dict[str, Any], tracker: FlightTaskTracker) -> TaskSnapshot:
    if message_type in {'fcs_datagcs', 'fcs_datagcs_view'}:
        return tracker.update(telemetry_payload=payload)
    if message_type in {'gcs_command', 'extu_fcs'}:
        return tracker.update(gcs_payload=payload)
    return tracker.update()