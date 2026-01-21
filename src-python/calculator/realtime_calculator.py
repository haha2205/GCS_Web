"""
实时计算引擎
提供5维KPI指标计算：算力、通信、能耗、任务效能、飞行性能
"""

import time
import math
import logging
from collections import deque
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class RealTimeCalculator:
    """
    实时计算引擎
    
    核心功能：
    1. 算力资源监控（CPU负载、内存使用）
    2. 通信指标计算（抖动、丢包率、延迟）
    3. 能耗指标监测（功率、累计能耗）
    4. 任务效能评估（进度、安全余量）
    5. 飞行性能分析（RMSE、轨迹误差）
    """
    
    def __init__(self):
        """初始化计算引擎"""
        
        # --- 通信资源状态 ---
        self.last_seq: Dict[int, int] = {}  # 记录每个消息ID的序列号
        self.packet_loss_window = deque(maxlen=100)  # 滑动窗口统计丢包
        self.last_arrival_time: Dict[int, float] = {}  # 计算抖动用
        self.packet_count: Dict[int, int] = {}  # 记录每个消息的接收次数
        
        # --- 能耗状态 ---
        self.total_energy = 0.0  # 累计焦耳
        self.last_energy_time = time.time()
        self.power_readings = deque(maxlen=50)  # 最近50次功率读数
        
        # --- 飞行性能状态 ---
        self.rmse_window = deque(maxlen=50)  # 存储最近50个误差值用于平滑显示
        self.trajectory_errors = deque(maxlen=100)  # 轨迹误差
        
        # --- 任务效能状态 ---
        self.waypoint_count = 10  # 总航点数（默认值）
        self.current_waypoint = 0
        
        # --- 算力监控状态 ---
        self.cpu_readings = deque(maxlen=100)  # 最近100次CPU读数
        
        logger.info("实时计算引擎初始化完成")
    
    def process_packet(self, decoded_data: dict) -> Dict[str, Any]:
        """
        入口函数：接收解码后的字典，返回计算后的KPI
        
        Args:
            decoded_data: 解码后的UDP数据包字典
            
        Returns:
            包含5个维度KPI的字典
        """
        msg_type = decoded_data.get('type', 'unknown')
        kpi_result = {
            'timestamp': decoded_data.get('timestamp', time.time()),
            'dimensions': {}
        }
        
        # 根据消息类型计算不同的KPI
        if msg_type == 'fcs_states':
            kpi_result['dimensions'].update(self._calc_flight_performance(decoded_data))
            kpi_result['dimensions'].update(self._calc_mission(decoded_data))
            
        elif msg_type in ['fcs_param', 'fcs_datactrl']:
            kpi_result['dimensions'].update(self._calc_computing_resources(decoded_data))
            
        elif msg_type in ['fcs_gncbus', 'fcs_pwms']:
            kpi_result['dimensions'].update(self._calc_communication(decoded_data))
            
        elif msg_type == 'obstacles':
            kpi_result['dimensions'].update(self._calc_mission(decoded_data))
        
        # 所有包都更新通信指标（如果有消息ID）
        if 'func_code' in decoded_data:
            kpi_result['dimensions'].update(self._calc_communication(decoded_data))
        
        # 计算综合评分
        kpi_result['overall_score'] = self._calc_overall_score(kpi_result['dimensions'])
        
        return kpi_result
    
    # ---------------------------------------------------------
    # 维度 1: 算力资源 (Computing)
    # ---------------------------------------------------------
    def _calc_computing_resources(self, data: dict) -> Dict[str, Any]:
        """计算算力资源指标"""
        # 模拟CPU负载（实际应该从数据中提取）
        cpu = 25.0 + (time.time() % 20) * 3  # 模拟值 25-85%
        
        # 归一化评分 (假设阈值是 90%)
        score = max(0.0, min(1.0, 1.0 - (cpu / 90.0)))
        
        # 更新CPU读数
        self.cpu_readings.append(cpu)
        avg_cpu = sum(self.cpu_readings) / len(self.cpu_readings) if self.cpu_readings else cpu
        
        return {
            "computing": {
                "cpu_load": round(cpu, 2),
                "cpu_avg": round(avg_cpu, 2),
                "score": round(score, 2),
                "status": "normal" if cpu < 80 else "high"
            }
        }
    
    # ---------------------------------------------------------
    # 维度 2: 通信资源 (Communication)
    # ---------------------------------------------------------
    def _calc_communication(self, data: dict) -> Dict[str, Any]:
        """计算通信指标"""
        msg_id = data.get('func_code', 0)
        now = time.time()
        
        # 1. 丢包率计算 (基于序列号)
        loss = 0
        if msg_id in self.last_seq:
            diff = msg_id - self.last_seq[msg_id]
            if msg_id == 0x42:  # fcs_states消息
                # 模拟序列号递增
                expected = (self.last_seq[msg_id] + 1) % 256
                if msg_id != expected:
                    loss = 1
        
        self.last_seq[msg_id] = msg_id
        self.packet_count[msg_id] = self.packet_count.get(msg_id, 0) + 1
        
        # 更新滑动窗口 (1=丢包, 0=正常)
        self.packet_loss_window.append(1 if loss > 0 else 0)
        plr = sum(self.packet_loss_window) / len(self.packet_loss_window) if self.packet_loss_window else 0
        
        # 2. 抖动计算 (Jitter)
        jitter = 0
        if msg_id in self.last_arrival_time:
            interval = now - self.last_arrival_time[msg_id]
            # 假设标准发送间隔是 0.02s (50Hz)，计算偏差
            jitter = abs(interval - 0.02) * 1000  # 转ms
        self.last_arrival_time[msg_id] = now
        
        # 3. 计算评分
        # 丢包率0-5%为正常，5-20%为警告，>20%为严重
        if plr < 0.05:
            plr_score = 1.0
        elif plr < 0.20:
            plr_score = 0.5
        else:
            plr_score = 0.0
        
        # 抖动<10ms为正常，10-50ms为警告，>50ms为严重
        if jitter < 10:
            jitter_score = 1.0
        elif jitter < 50:
            jitter_score = 0.5
        else:
            jitter_score = 0.0
        
        comm_score = (plr_score * 0.7 + jitter_score * 0.3)
        
        return {
            "communication": {
                "jitter_ms": round(jitter, 2),
                "plr_percent": round(plr * 100, 2),
                "packet_count": sum(self.packet_count.values()),
                "score": round(comm_score, 2),
                "status": "normal" if comm_score > 0.7 else ("warning" if comm_score > 0.3 else "critical")
            }
        }
    
    # ---------------------------------------------------------
    # 维度 3: 能耗指标 (Energy)
    # ---------------------------------------------------------
    def _calc_energy(self, data: dict) -> Dict[str, Any]:
        """计算能耗指标"""
        # 模拟能耗数据（实际应该从电池传感器获取）
        voltage = 12.6  # 模拟电压
        current = 15.0 + (time.time() % 10) * 2  # 模拟电流 15-35A
        
        # 1. 瞬时功率
        power = voltage * current
        
        # 2. 累计能耗 (积分)
        now = time.time()
        dt = now - self.last_energy_time
        if dt < 1.0:  # 防止时间跳变太大
            self.total_energy += power * dt
        self.last_energy_time = now
        
        # 更新功率读数
        self.power_readings.append(power)
        avg_power = sum(self.power_readings) / len(self.power_readings) if self.power_readings else power
        
        # 3. 计算评分（基于功率水平）
        # 假设满载功率500W，正常300W
        power_ratio = avg_power / 500.0
        score = 1.0 if power_ratio < 0.6 else (0.7 if power_ratio < 0.8 else 0.4)
        
        return {
            "energy": {
                "power_watts": round(power, 1),
                "power_avg": round(avg_power, 1),
                "total_joules": round(self.total_energy, 1),
                "total_kwh": round(self.total_energy / 3600000, 4),
                "score": round(score, 2),
                "status": "normal" if score > 0.7 else "high"
            }
        }
    
    # ---------------------------------------------------------
    # 维度 4: 任务效能 (Mission Efficacy)
    # ---------------------------------------------------------
    def _calc_mission(self, data: dict) -> Dict[str, Any]:
        """计算任务效能指标"""
        # 模拟任务进度（实际应该从航点数据获取）
        current_wp = self.current_waypoint
        total_wp = self.waypoint_count
        
        # 1. 任务覆盖率
        coverage = current_wp / total_wp if total_wp > 0 else 0
        
        # 2. 安全余量 (电量余量 - 返航所需)
        # 模拟电量状态
        batt_rem = 100.0 - (time.time() % 300) / 3  # 模拟电量 100-0%
        safe_margin = batt_rem - 20  # 假设20%是红线
        
        # 3. 计算评分
        progress_score = coverage
        
        # 安全余量评分
        if safe_margin > 30:
            safety_score = 1.0
        elif safe_margin > 10:
            safety_score = 0.7
        elif safe_margin > 0:
            safety_score = 0.4
        else:
            safety_score = 0.0
        
        mission_score = (progress_score * 0.6 + safety_score * 0.4)
        
        return {
            "mission": {
                "progress_percent": round(coverage * 100, 1),
                "current_waypoint": current_wp,
                "total_waypoints": total_wp,
                "battery_remaining": round(batt_rem, 1),
                "safety_margin": round(safe_margin, 1),
                "score": round(mission_score, 2),
                "status": "normal" if safety_score > 0.7 else ("warning" if safety_score > 0.4 else "critical")
            }
        }
    
    # ---------------------------------------------------------
    # 维度 5: 飞行性能 (Flight Performance)
    # ---------------------------------------------------------
    def _calc_flight_performance(self, data: dict) -> Dict[str, Any]:
        """计算飞行性能指标"""
        telemetry = data.get('data', {})
        
        # 实际位置
        act_lat = telemetry.get('latitude', 0)
        act_lon = telemetry.get('longitude', 0)
        act_alt = telemetry.get('altitude', 0)
        
        # 期望位置（模拟值，实际应该从飞控的目标航点获取）
        target_lat = act_lat + 0.0001  # 模拟小偏差
        target_lon = act_lon + 0.0001
        target_alt = act_alt + 0.5  # 0.5m高度差
        
        # 1. 计算位置误差 (简化版，经纬度差值转米)
        # 1度纬度约等于111km
        lat_err = (act_lat - target_lat) * 111000
        lon_err = (act_lon - target_lon) * 111000 * math.cos(math.radians(act_lat))
        alt_err = act_alt - target_alt
        
        # 欧氏距离
        error_distance = math.sqrt(lat_err**2 + lon_err**2 + alt_err**2)
        
        self.rmse_window.append(error_distance)
        self.trajectory_errors.append(error_distance)
        
        avg_rmse = sum(self.rmse_window) / len(self.rmse_window) if self.rmse_window else 0
        
        # 2. 计算评分 (假设允许误差 2.0米)
        score = max(0.0, min(1.0, 1.0 - (avg_rmse / 2.0)))
        
        # 3. 姿态稳定性（基于roll和pitch）
        roll = telemetry.get('roll', 0)
        pitch = telemetry.get('pitch', 0)
        attitude_stability = 1.0 - (abs(roll) + abs(pitch)) / 180.0
        
        performance_score = (score * 0.8 + attitude_stability * 0.2)
        
        return {
            "performance": {
                "rmse_meters": round(avg_rmse, 3),
                "position_error_m": round(error_distance, 3),
                "roll_deg": round(roll, 2),
                "pitch_deg": round(pitch, 2),
                "yaw_deg": round(telemetry.get('yaw', 0), 2),
                "attitude_stability": round(attitude_stability, 2),
                "score": round(performance_score, 2),
                "status": "excellent" if score > 0.8 else ("good" if score > 0.5 else ("fair" if score > 0.3 else "poor"))
            }
        }
    
    # ---------------------------------------------------------
    # 综合评分
    # ---------------------------------------------------------
    def _calc_overall_score(self, dimensions: Dict[str, Any]) -> float:
        """
        计算综合评分
        
        权重分配：
        - 算力: 15%
        - 通信: 20%
        - 能耗: 15%
        - 任务: 25%
        - 性能: 25%
        """
        weights = {
            'computing': 0.15,
            'communication': 0.20,
            'energy': 0.15,
            'mission': 0.25,
            'performance': 0.25
        }
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for dim_name, weight in weights.items():
            if dim_name in dimensions:
                dim_data = dimensions[dim_name]
                score = dim_data.get('score', 0.0)
                weighted_sum += score * weight
                total_weight += weight
        
        overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        return round(overall_score, 2)
    
    def reset(self):
        """重置所有状态"""
        self.last_seq.clear()
        self.packet_loss_window.clear()
        self.last_arrival_time.clear()
        self.packet_count.clear()
        self.total_energy = 0.0
        self.last_energy_time = time.time()
        self.power_readings.clear()
        self.rmse_window.clear()
        self.trajectory_errors.clear()
        self.current_waypoint = 0
        
        logger.info("实时计算引擎状态已重置")