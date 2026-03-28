"""
实时计算引擎
基于协议字段计算监控与任务评价指标。
"""

import time
import math
import logging
from collections import defaultdict, deque
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


EXPECTED_PERIOD_MS = {
    0x41: 20.0,
    0x42: 20.0,
    0x43: 20.0,
    0x44: 20.0,
    0x4B: 20.0,
    0x71: 100.0,
}

BUS_CAPACITY_BYTES_PER_SEC = 1_250_000.0
CONTROL_JITTER_FUNC_CODES = {0x42, 0x43, 0x44}


class RealTimeCalculator:
    """基于协议包持续更新关键指标。"""

    def __init__(self):
        self.packet_times = defaultdict(lambda: deque(maxlen=200))
        self.packet_intervals_ms = defaultdict(lambda: deque(maxlen=60))
        self.packet_bytes = deque(maxlen=1500)
        self.control_jitter_samples = deque(maxlen=400)
        self.tracking_error_window = deque(maxlen=200)
        self.roll_abs_window = deque(maxlen=200)
        self.planning_time_window = deque(maxlen=120)
        self.perception_latency_window = deque(maxlen=120)
        self.perception_cpu_window = deque(maxlen=120)
        self.obstacle_count_window = deque(maxlen=120)
        self.system_power_window = deque(maxlen=120)

        self.latest_fcs_states: Dict[str, Any] = {}
        self.latest_gncbus: Dict[str, Any] = {}
        self.latest_datagcs: Dict[str, Any] = {}
        self.latest_avoiflag: Dict[str, Any] = {}
        self.latest_esc: Dict[str, Any] = {}
        self.latest_line_aim2ab: Dict[str, Any] = {}
        self.latest_line_ab: Dict[str, Any] = {}
        self.latest_planning: Dict[str, Any] = {}

        self.last_sequence = defaultdict(lambda: None)
        self.seq_total_received = defaultdict(int)
        self.seq_total_missing = defaultdict(int)
        self.last_planning_arrival: Optional[float] = None
        self.last_avoidance_flag = False
        self.last_mission_id: Optional[int] = None
        self.avoid_trigger_count = 0
        self.mission_switch_count = 0

        self.total_energy_j = 0.0
        self.last_energy_time = time.time()

        logger.info("实时计算引擎初始化完成")

    def process_packet(self, decoded_data: dict) -> Dict[str, Any]:
        now = time.time()
        msg_type = decoded_data.get('type', 'unknown')
        payload = decoded_data.get('data', {}) or {}

        self._update_packet_stats(decoded_data, now)

        if msg_type == 'fcs_states':
            self._update_fcs_states(payload)
        elif msg_type == 'fcs_gncbus':
            self.latest_gncbus = payload
        elif msg_type == 'fcs_datagcs':
            self._update_datagcs(payload)
        elif msg_type == 'avoiflag':
            self._update_avoiflag(payload)
        elif msg_type == 'fcs_esc':
            self.latest_esc = payload
        elif msg_type == 'fcs_line_aim2ab':
            self.latest_line_aim2ab = payload
        elif msg_type == 'fcs_line_ab':
            self.latest_line_ab = payload
        elif msg_type == 'planning_telemetry':
            self._update_planning(payload, now)

        indicators = self._compute_indicators()
        dimensions = self._build_dimensions(indicators)
        overall_score = self._calc_overall_score(dimensions)
        window_metrics = self._build_window_metrics(indicators)

        return {
            'timestamp': decoded_data.get('timestamp', int(now * 1000)),
            'dimensions': dimensions,
            'indicators': indicators,
            'window_metrics': window_metrics,
            'views': {
                'flight_state': self._build_flight_state_view(),
                'planning_state': self._build_planning_state_view(),
                'system_performance': self._build_system_performance_view(window_metrics, indicators),
            },
            'overallScore': overall_score,
            'overall_score': overall_score,
        }

    def _update_packet_stats(self, decoded_data: dict, now: float) -> None:
        func_code = decoded_data.get('func_code')
        if func_code is None:
            return

        payload = decoded_data.get('data', {}) or {}
        payload_size = len(str(payload).encode('utf-8'))
        self.packet_bytes.append((now, payload_size, func_code))
        self.packet_times[func_code].append(now)

        times = self.packet_times[func_code]
        if func_code in CONTROL_JITTER_FUNC_CODES and len(times) >= 2:
            interval_ms = (times[-1] - times[-2]) * 1000.0
            if interval_ms > 0:
                interval_window = self.packet_intervals_ms[func_code]
                interval_window.append(interval_ms)
                if len(interval_window) >= 5:
                    baseline_ms = float(np.median(list(interval_window)))
                    self.control_jitter_samples.append(abs(interval_ms - baseline_ms))

        seq_id = payload.get('seq_id')
        if seq_id is not None:
            seq_id = int(seq_id)
            last_seq = self.last_sequence[func_code]
            if last_seq is not None and seq_id > last_seq + 1:
                self.seq_total_missing[func_code] += seq_id - last_seq - 1
            self.last_sequence[func_code] = seq_id
            self.seq_total_received[func_code] += 1

    def _update_fcs_states(self, payload: Dict[str, Any]) -> None:
        self.latest_fcs_states = payload

        roll_deg = self._angle_to_degrees(payload.get('states_phi', payload.get('roll', 0)))
        self.roll_abs_window.append(abs(roll_deg))

        voltage = payload.get('battery_voltage', payload.get('voltage'))
        current = payload.get('battery_current', payload.get('current'))
        if voltage is not None and current is not None:
            voltage = self._safe_number(voltage)
            current = self._safe_number(current)
            power = max(0.0, voltage * current)
            now = time.time()
            dt = max(0.0, min(1.0, now - self.last_energy_time))
            self.total_energy_j += power * dt
            self.last_energy_time = now
            self.system_power_window.append(power)

    def _update_datagcs(self, payload: Dict[str, Any]) -> None:
        self.latest_datagcs = payload
        mission_id = payload.get('Tele_GCS_Mission', payload.get('Mission'))
        if mission_id is not None:
            mission_id = int(self._safe_number(mission_id, 0))
            if self.last_mission_id is not None and mission_id != self.last_mission_id:
                self.mission_switch_count += 1
            self.last_mission_id = mission_id

    def _update_avoiflag(self, payload: Dict[str, Any]) -> None:
        self.latest_avoiflag = payload
        avoid_now = self._safe_bool(
            payload.get('AvoiFlag_AvoidanceFlag', payload.get('avoidance_flag', False))
        )
        if avoid_now and not self.last_avoidance_flag:
            self.avoid_trigger_count += 1
        self.last_avoidance_flag = avoid_now

    def _update_planning(self, payload: Dict[str, Any], now: float) -> None:
        self.latest_planning = payload
        self.obstacle_count_window.append(self._safe_number(payload.get('obstacle_count', 0)))

        planning_time_ms = self._extract_planning_time_ms(payload)
        if planning_time_ms is not None and planning_time_ms >= 0:
            self.planning_time_window.append(planning_time_ms)

        self.last_planning_arrival = now

        tracking_error = self._compute_path_tracking_error(payload)
        if tracking_error is not None:
            self.tracking_error_window.append(tracking_error)

    def _compute_indicators(self) -> Dict[str, float]:
        perception_latency = self._window_mean(self.perception_latency_window)
        perception_cpu_load = self._window_mean(self.perception_cpu_window)
        obstacle_count = self._window_mean(self.obstacle_count_window)

        tracking_rmse = self._window_rmse(self.tracking_error_window)
        planning_time_ms = self._window_mean(self.planning_time_window)
        control_jitter_ms = self._window_p95(self.control_jitter_samples)
        attitude_overshoot = min(300.0, max(self.roll_abs_window) / 30.0 * 100.0) if self.roll_abs_window else 0.0

        planning_recv = self.seq_total_received[0x71]
        planning_missing = self.seq_total_missing[0x71]
        downlink_loss = planning_missing / (planning_recv + planning_missing) if (planning_recv + planning_missing) else 0.0

        bus_bandwidth_util = self._estimate_bus_bandwidth_util()
        cross_latency_ms = 0.2 + bus_bandwidth_util * 12.0 + planning_time_ms * 0.02
        serial_cost = min(1.0, bus_bandwidth_util * 1.5)

        system_power = self._window_mean(self.system_power_window, default=240.0)
        resource_margin = max(0.0, 1.0 - min(1.2, max(0.12, perception_cpu_load)) / 0.9)
        dal_compliance = 1.0
        mission_reliability = min(
            0.999,
            max(0.0, 0.99 * dal_compliance * (1.0 - downlink_loss * 0.5) * (1.0 - min(1.0, tracking_rmse / 20.0) * 0.3))
        )

        return {
            'Ind_Perception_Latency': round(perception_latency, 3),
            'Ind_Obstacle_Count': round(obstacle_count, 3),
            'Ind_Perception_CPU_Load': round(perception_cpu_load, 4),
            'Ind_Tracking_RMSE': round(tracking_rmse, 4),
            'Ind_Avoid_Success': 1.0,
            'Ind_Planning_Time': round(planning_time_ms, 3),
            'Ind_Control_Jitter': round(control_jitter_ms, 3),
            'Ind_Attitude_Overshoot': round(attitude_overshoot, 3),
            'Ind_Motor_Response': 2.0,
            'Ind_Downlink_Loss': round(downlink_loss, 6),
            'Ind_Uplink_Delay': 10.0,
            'Ind_Cross_Latency': round(cross_latency_ms, 3),
            'Ind_Serial_Cost': round(serial_cost, 4),
            'Ind_Bus_Bandwidth': round(bus_bandwidth_util, 6),
            'Ind_DAL_Compliance': dal_compliance,
            'Ind_System_Power': round(system_power, 3),
            'Ind_Resource_Margin': round(resource_margin, 4),
            'Ind_Mission_Reliability': round(mission_reliability, 6),
        }

    def _build_window_metrics(self, indicators: Dict[str, float]) -> Dict[str, Any]:
        cmd_idx = int(self._safe_number(self.latest_datagcs.get('Tele_GCS_CmdIdx', 0), 0))
        mission_id = int(self._safe_number(self.latest_datagcs.get('Tele_GCS_Mission', 0), 0))
        next_waypoint = self.latest_line_aim2ab.get('next_dot', self.latest_line_aim2ab.get('ac_aim2AB_next_dot', 0))
        planner_cycle_hz = self._estimate_packet_frequency(0x71)
        radar_fps = self._estimate_packet_frequency(0x50)
        attitude_peak_phi_deg = round(max(self.roll_abs_window) if self.roll_abs_window else 0.0, 3)
        esc_power_pct_avg = round(self._average_list(self.latest_esc.get('power_ratings', [])), 3)
        tracking_rmse = indicators['Ind_Tracking_RMSE'] if self.tracking_error_window else None
        planning_time_ms = indicators['Ind_Planning_Time'] if self.planning_time_window else None
        control_jitter_ms = indicators['Ind_Control_Jitter'] if self.control_jitter_samples else None
        perception_latency_ms = indicators['Ind_Perception_Latency'] if self.perception_latency_window else None
        planner_cycle_hz = round(planner_cycle_hz, 3) if planner_cycle_hz > 0 else None
        radar_fps = round(radar_fps, 3) if radar_fps > 0 else None

        return {
            'tracking_rmse': tracking_rmse,
            'planning_time_ms': planning_time_ms,
            'control_jitter_ms': control_jitter_ms,
            'perception_latency_ms': perception_latency_ms,
            'obstacle_count': indicators['Ind_Obstacle_Count'],
            'planner_cycle_hz': planner_cycle_hz,
            'radar_fps': radar_fps,
            'attitude_peak_phi_deg': attitude_peak_phi_deg,
            'cmd_idx': cmd_idx,
            'mission_id': mission_id,
            'avoid_flag': self._safe_bool(
                self.latest_avoiflag.get('AvoiFlag_AvoidanceFlag', self.latest_avoiflag.get('avoidance_flag', False))
            ),
            'avoid_trigger_count': self.avoid_trigger_count,
            'mission_switch_count': self.mission_switch_count,
            'next_waypoint': int(self._safe_number(next_waypoint, 0)),
            'esc_power_pct': esc_power_pct_avg,
            'esc_power_pct_avg': esc_power_pct_avg,
        }

    def _build_flight_state_view(self) -> Dict[str, Any]:
        state = self.latest_fcs_states
        return {
            'latitude': self._safe_number(state.get('states_lat', 0.0), 0.0),
            'longitude': self._safe_number(state.get('states_lon', 0.0), 0.0),
            'height': self._safe_number(state.get('states_height', 0.0), 0.0),
            'vx': self._safe_number(state.get('states_Vx_GS', 0.0), 0.0),
            'vy': self._safe_number(state.get('states_Vy_GS', 0.0), 0.0),
            'vz': self._safe_number(state.get('states_Vz_GS', 0.0), 0.0),
            'p_rate': self._display_angle(state.get('states_p', 0.0)),
            'q_rate': self._display_angle(state.get('states_q', 0.0)),
            'r_rate': self._display_angle(state.get('states_r', 0.0)),
            'phi': round(self._safe_number(state.get('states_phi', 0.0), 0.0), 3),
            'theta': round(self._safe_number(state.get('states_theta', 0.0), 0.0), 3),
            'psi': round(self._safe_number(state.get('states_psi', 0.0), 0.0), 3),
            'raw': {
                'states_p': self._safe_number(state.get('states_p', 0.0), 0.0),
                'states_q': self._safe_number(state.get('states_q', 0.0), 0.0),
                'states_r': self._safe_number(state.get('states_r', 0.0), 0.0),
                'states_phi': self._safe_number(state.get('states_phi', 0.0), 0.0),
                'states_theta': self._safe_number(state.get('states_theta', 0.0), 0.0),
                'states_psi': self._safe_number(state.get('states_psi', 0.0), 0.0),
            },
        }

    def _build_planning_state_view(self) -> Dict[str, Any]:
        planning = self.latest_planning
        datagcs = self.latest_datagcs
        aim2ab = self.latest_line_aim2ab
        line_ab = self.latest_line_ab
        avoiflag = self.latest_avoiflag
        position = planning.get('position', {}) if isinstance(planning.get('position', {}), dict) else {}
        local_path = planning.get('local_path') or planning.get('local_traj') or []
        global_path = planning.get('global_path') or []
        obstacles = planning.get('obstacles') or []
        return {
            'cmd_idx': int(self._safe_number(datagcs.get('Tele_GCS_CmdIdx', datagcs.get('CmdIdx', 0)), 0)),
            'mission_id': int(self._safe_number(datagcs.get('Tele_GCS_Mission', datagcs.get('Mission', 0)), 0)),
            'mission_value': self._safe_number(datagcs.get('Tele_GCS_Val', datagcs.get('Val', 0.0)), 0.0),
            'gcs_link_fail': self._safe_bool(datagcs.get('Tele_GCS_com_GCS_fail', datagcs.get('fail', False))),
            'avoid_enabled': self._safe_bool(avoiflag.get('AvoiFlag_LaserRadar_Enabled', False)),
            'avoid_triggered': self._safe_bool(avoiflag.get('AvoiFlag_AvoidanceFlag', False)),
            'guide_flag': self._safe_bool(avoiflag.get('AvoiFlag_GuideFlag', False)),
            'next_waypoint': int(self._safe_number(aim2ab.get('next_dot', aim2ab.get('ac_aim2AB_next_dot', 0)), 0)),
            'next_segment_index': int(self._safe_number(aim2ab.get('next_num', aim2ab.get('ac_aim2AB_next_num', 0)), 0)),
            'ab_next_waypoint': int(self._safe_number(line_ab.get('next_dot', line_ab.get('acAB_next_dot', 0)), 0)),
            'planning_status': int(self._safe_number(planning.get('status', 0), 0)),
            'global_path_count': int(self._safe_number(planning.get('global_path_count', 0), 0)),
            'local_traj_count': int(self._safe_number(planning.get('local_traj_count', 0), 0)),
            'obstacle_count': int(self._safe_number(planning.get('obstacle_count', 0), 0)),
            'current_pos_x': self._safe_number(planning.get('current_pos_x', position.get('x')), 0.0),
            'current_pos_y': self._safe_number(planning.get('current_pos_y', position.get('y')), 0.0),
            'current_pos_z': self._safe_number(planning.get('current_pos_z', position.get('z')), 0.0),
            'global_path': global_path if isinstance(global_path, list) else [],
            'local_path': local_path if isinstance(local_path, list) else [],
            'local_traj': local_path if isinstance(local_path, list) else [],
            'obstacles': obstacles if isinstance(obstacles, list) else [],
        }

    def _build_system_performance_view(self, window_metrics: Dict[str, Any], indicators: Dict[str, float]) -> Dict[str, Any]:
        esc_rpms = self.latest_esc.get('rpms', []) if isinstance(self.latest_esc, dict) else []
        esc_powers = self.latest_esc.get('power_ratings', []) if isinstance(self.latest_esc, dict) else []
        trusted_metrics = {
            'planner_cycle_hz': window_metrics['planner_cycle_hz'],
            'radar_fps': window_metrics.get('radar_fps'),
            'perception_latency_ms': window_metrics['perception_latency_ms'],
            'obstacle_count': window_metrics['obstacle_count'],
            'avoid_trigger_count': window_metrics['avoid_trigger_count'],
            'mission_switch_count': window_metrics['mission_switch_count'],
            'next_waypoint': window_metrics['next_waypoint'],
            'esc_power_pct_avg': window_metrics.get('esc_power_pct_avg', window_metrics['esc_power_pct']),
            'esc_rpm_avg': round(self._average_list(esc_rpms), 3),
            'esc_rpm_max': round(max([self._safe_number(value, 0.0) for value in esc_rpms], default=0.0), 3),
            'esc_power_max': round(max([self._safe_number(value, 0.0) for value in esc_powers], default=0.0), 3),
            'downlink_loss_rate': indicators['Ind_Downlink_Loss'],
        }
        derived_metrics = {
            'planning_time_ms': window_metrics['planning_time_ms'],
            'tracking_rmse': window_metrics['tracking_rmse'],
            'control_jitter_ms': window_metrics['control_jitter_ms'],
            'attitude_peak_phi_deg': window_metrics.get('attitude_peak_phi_deg'),
        }
        metric_quality = {
            'planner_cycle_hz': 'trusted',
            'radar_fps': 'trusted',
            'perception_latency_ms': 'trusted',
            'obstacle_count': 'trusted',
            'avoid_trigger_count': 'trusted',
            'mission_switch_count': 'trusted',
            'next_waypoint': 'trusted',
            'esc_power_pct_avg': 'trusted',
            'esc_rpm_avg': 'trusted',
            'esc_rpm_max': 'trusted',
            'esc_power_max': 'trusted',
            'downlink_loss_rate': 'trusted',
            'planning_time_ms': 'derived' if window_metrics['planning_time_ms'] is not None else 'unavailable',
            'tracking_rmse': 'derived' if window_metrics['tracking_rmse'] is not None else 'unavailable',
            'control_jitter_ms': 'derived' if window_metrics['control_jitter_ms'] is not None else 'unavailable',
            'attitude_peak_phi_deg': 'derived',
        }
        return {
            'perception_latency_ms': window_metrics['perception_latency_ms'],
            'planning_time_ms': window_metrics['planning_time_ms'],
            'tracking_rmse': window_metrics['tracking_rmse'],
            'control_jitter_ms': window_metrics['control_jitter_ms'],
            'planner_cycle_hz': window_metrics['planner_cycle_hz'],
            'radar_fps': window_metrics.get('radar_fps', 0.0),
            'attitude_peak_phi_deg': window_metrics.get('attitude_peak_phi_deg', 0.0),
            'obstacle_count': window_metrics['obstacle_count'],
            'avoid_trigger_count': window_metrics['avoid_trigger_count'],
            'mission_switch_count': window_metrics['mission_switch_count'],
            'cmd_idx': window_metrics['cmd_idx'],
            'mission_id': window_metrics['mission_id'],
            'esc_power_pct': window_metrics['esc_power_pct'],
            'esc_power_pct_avg': window_metrics.get('esc_power_pct_avg', window_metrics['esc_power_pct']),
            'esc_rpm_avg': trusted_metrics['esc_rpm_avg'],
            'esc_rpm_max': trusted_metrics['esc_rpm_max'],
            'esc_power_max': trusted_metrics['esc_power_max'],
            'downlink_loss_rate': indicators['Ind_Downlink_Loss'],
            'trusted': trusted_metrics,
            'derived': derived_metrics,
            'metric_quality': metric_quality,
        }

    def _build_dimensions(self, indicators: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        computing_score = np.mean([
            indicators['Ind_Resource_Margin'],
            max(0.0, 1.0 - min(1.0, indicators['Ind_Perception_CPU_Load'])),
        ])

        communication_score = np.mean([
            max(0.0, 1.0 - min(1.0, indicators['Ind_Control_Jitter'] / 20.0)),
            1.0 - indicators['Ind_Downlink_Loss'],
            max(0.0, 1.0 - min(1.0, indicators['Ind_Bus_Bandwidth'])),
        ])

        energy_score = max(0.0, 1.0 - min(1.0, indicators['Ind_System_Power'] / 1200.0))

        mission_score = np.mean([
            max(0.0, 1.0 - min(1.0, indicators['Ind_Tracking_RMSE'] / 10.0)),
            max(0.0, 1.0 - min(1.0, indicators['Ind_Planning_Time'] / 500.0)),
            indicators['Ind_Mission_Reliability'],
        ])

        performance_score = np.mean([
            max(0.0, 1.0 - min(1.0, indicators['Ind_Perception_Latency'] / 200.0)),
            max(0.0, 1.0 - min(1.0, indicators['Ind_Attitude_Overshoot'] / 100.0)),
            max(0.0, 1.0 - min(1.0, indicators['Ind_Motor_Response'] / 20.0)),
        ])

        return {
            'computing': {
                'perception_cpu_load': indicators['Ind_Perception_CPU_Load'],
                'resource_margin': indicators['Ind_Resource_Margin'],
                'score': round(float(computing_score), 3),
                'status': 'normal' if computing_score >= 0.65 else 'warning',
            },
            'communication': {
                'jitter_ms': indicators['Ind_Control_Jitter'],
                'downlink_loss_rate': indicators['Ind_Downlink_Loss'],
                'bus_bandwidth_util': indicators['Ind_Bus_Bandwidth'],
                'cross_latency_ms': indicators['Ind_Cross_Latency'],
                'score': round(float(communication_score), 3),
                'status': 'normal' if communication_score >= 0.65 else 'warning',
            },
            'energy': {
                'system_power_w': indicators['Ind_System_Power'],
                'score': round(float(energy_score), 3),
                'status': 'normal' if energy_score >= 0.5 else 'warning',
            },
            'mission': {
                'tracking_rmse_m': indicators['Ind_Tracking_RMSE'],
                'planning_time_ms': indicators['Ind_Planning_Time'],
                'mission_reliability': indicators['Ind_Mission_Reliability'],
                'score': round(float(mission_score), 3),
                'status': 'normal' if mission_score >= 0.65 else 'warning',
            },
            'performance': {
                'perception_latency_ms': indicators['Ind_Perception_Latency'],
                'attitude_overshoot_pct': indicators['Ind_Attitude_Overshoot'],
                'motor_response_ms': indicators['Ind_Motor_Response'],
                'score': round(float(performance_score), 3),
                'status': 'normal' if performance_score >= 0.65 else 'warning',
            },
        }

    def _estimate_bus_bandwidth_util(self) -> float:
        now = time.time()
        recent = [(ts, size) for ts, size, _ in self.packet_bytes if now - ts <= 5.0]
        if not recent:
            return 0.0
        total_bytes = sum(size for _, size in recent)
        bytes_per_sec = total_bytes / 5.0
        return min(1.0, bytes_per_sec / BUS_CAPACITY_BYTES_PER_SEC)

    def _estimate_packet_frequency(self, func_code: int, window_seconds: float = 5.0) -> float:
        now = time.time()
        times = [ts for ts in self.packet_times.get(func_code, []) if now - ts <= window_seconds]
        if len(times) < 2:
            return 0.0
        duration = times[-1] - times[0]
        if duration <= 0:
            return 0.0
        return (len(times) - 1) / duration

    def _compute_path_tracking_error(self, payload: Dict[str, Any]) -> Optional[float]:
        pos_x = self._safe_number(payload.get('current_pos_x', self._nested_get(payload, 'position', 'x')), None)
        pos_y = self._safe_number(payload.get('current_pos_y', self._nested_get(payload, 'position', 'y')), None)
        pos_z = self._safe_number(payload.get('current_pos_z', self._nested_get(payload, 'position', 'z')), None)

        if pos_x is None or pos_y is None or pos_z is None:
            return None

        path_points = payload.get('local_path') or payload.get('local_traj') or payload.get('global_path') or []
        if not isinstance(path_points, list) or not path_points:
            return None

        distances = []
        for point in path_points:
            point_x = self._safe_number(point.get('x', self._nested_get(point, 'position', 'x')), None)
            point_y = self._safe_number(point.get('y', self._nested_get(point, 'position', 'y')), None)
            point_z = self._safe_number(point.get('z', self._nested_get(point, 'position', 'z')), 0.0)
            if point_x is None or point_y is None:
                continue
            distances.append(math.sqrt((pos_x - point_x) ** 2 + (pos_y - point_y) ** 2 + (pos_z - point_z) ** 2))

        return min(distances) if distances else None

    def _extract_planning_time_ms(self, payload: Dict[str, Any]) -> Optional[float]:
        candidate_keys = [
            'planning_time_ms',
            'planner_time_ms',
            'solve_time_ms',
            'processing_time_ms',
            'latency_ms',
        ]

        for key in candidate_keys:
            value = self._safe_number(payload.get(key), None)
            if value is not None:
                return value

        performance_payload = payload.get('performance')
        if isinstance(performance_payload, dict):
            for key in candidate_keys:
                value = self._safe_number(performance_payload.get(key), None)
                if value is not None:
                    return value

        return None

    def _calc_overall_score(self, dimensions: Dict[str, Dict[str, Any]]) -> float:
        weights = {
            'computing': 0.15,
            'communication': 0.25,
            'energy': 0.10,
            'mission': 0.25,
            'performance': 0.25,
        }

        weighted_sum = 0.0
        total_weight = 0.0
        for name, weight in weights.items():
            if name in dimensions:
                weighted_sum += dimensions[name].get('score', 0.0) * weight
                total_weight += weight
        return round(weighted_sum / total_weight if total_weight else 0.0, 3)

    def reset(self):
        self.__init__()

    @staticmethod
    def _nested_get(payload: Dict[str, Any], key: str, nested_key: str) -> Any:
        value = payload.get(key, {})
        if isinstance(value, dict):
            return value.get(nested_key)
        return None

    @staticmethod
    def _safe_number(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
        if value is None:
            return default
        try:
            parsed = float(value)
            if math.isfinite(parsed):
                return parsed
        except (TypeError, ValueError):
            pass
        return default

    @staticmethod
    def _angle_to_degrees(value: Any) -> float:
        numeric_value = RealTimeCalculator._safe_number(value, 0.0)
        if numeric_value is None:
            return 0.0
        if abs(numeric_value) <= (2 * math.pi + 0.5):
            return math.degrees(numeric_value)
        return numeric_value

    @staticmethod
    def _display_angle(value: Any) -> float:
        return round(RealTimeCalculator._angle_to_degrees(value), 3)

    @staticmethod
    def _safe_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value in (1, '1', 'true', 'True', 'TRUE'):
            return True
        if value in (0, '0', 'false', 'False', 'FALSE', None, ''):
            return False
        try:
            return bool(int(value))
        except (TypeError, ValueError):
            return bool(value)

    @staticmethod
    def _average_list(values: Iterable[Any]) -> float:
        numeric_values = [RealTimeCalculator._safe_number(value, 0.0) for value in values]
        numeric_values = [value for value in numeric_values if value is not None]
        return float(np.mean(numeric_values)) if numeric_values else 0.0

    @staticmethod
    def _window_mean(values: Iterable[float], default: float = 0.0) -> float:
        values = list(values)
        return float(np.mean(values)) if values else default

    @staticmethod
    def _window_p95(values: Iterable[float]) -> float:
        values = list(values)
        return float(np.percentile(values, 95)) if values else 0.0

    @staticmethod
    def _window_rmse(values: Iterable[float]) -> float:
        values = list(values)
        return math.sqrt(float(np.mean(np.square(values)))) if values else 0.0