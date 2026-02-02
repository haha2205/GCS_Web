"""
实时计算引擎
提供5维KPI指标计算：算力、通信、能耗、任务效能、飞行性能
"""

import time
import math
import logging
import numpy as np
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
        self.packet_intervals: Dict[int, deque] = {} # 记录每个消息的到达间隔
        
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
        self.safety_margins = deque(maxlen=50) # 安全余量
        
        # --- 算力监控状态 ---
        self.cpu_readings = deque(maxlen=100)  # 最近100次CPU读数
        self.mem_readings = deque(maxlen=100)  # 最近100次内存读数
        
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
        
        # 1. 基础通信统计更新 (所有包)
        if 'func_code' in decoded_data:
            self._update_comm_stats(decoded_data)
        
        # 2. 根据消息类型计算特定KPI
        if msg_type == 'fcs_states':
            kpi_result['dimensions'].update(self._calc_flight_performance(decoded_data))
            # 状态包通常包含电量信息
            kpi_result['dimensions'].update(self._calc_energy(decoded_data)) 
            
        elif msg_type == 'planning_telemetry': # 规划遥测
            kpi_result['dimensions'].update(self._calc_mission(decoded_data))

        elif msg_type in ['fcs_param', 'resources']:
            kpi_result['dimensions'].update(self._calc_computing_resources(decoded_data))
            # 资源包可能包含精确的电压电流
            kpi_result['dimensions'].update(self._calc_energy(decoded_data))
            
        elif msg_type in ['fcs_gncbus', 'fcs_pwms', 'bus_traffic']:
            # 这些包主要贡献通信统计，上面 _update_comm_stats 已处理
            pass
            
        elif msg_type == 'obstacles':
            # 障碍物信息更新
            pass
        
        # 3. 总是返回最新的通信摘要
        kpi_result['dimensions'].update(self._get_comm_summary())
        
        # 4. 如果没有获得某些维度的更新，使用缓存值或默认值填充 (避免前端闪烁)
        # (可选优化，这里暂不处理，前端通常会缓存)

        # 5. 计算综合评分
        kpi_result['overall_score'] = self._calc_overall_score(kpi_result['dimensions'])
        
        return kpi_result

    def _update_comm_stats(self, data: dict):
        """更新基础通信统计"""
        msg_id = data.get('func_code', 0)
        curr_time = time.time()
        
        # 1. 统计接收计数
        self.packet_count[msg_id] = self.packet_count.get(msg_id, 0) + 1
        
        # 2. 计算间隔（用于抖动分析）
        if msg_id in self.last_arrival_time:
            interval = curr_time - self.last_arrival_time[msg_id]
            if msg_id not in self.packet_intervals:
                self.packet_intervals[msg_id] = deque(maxlen=50)
            self.packet_intervals[msg_id].append(interval)
        self.last_arrival_time[msg_id] = curr_time

    def _get_comm_summary(self) -> Dict[str, Any]:
        """获取当前通信状态摘要"""
        # 计算平均抖动
        total_jitter = 0.0
        count = 0
        for intervals in self.packet_intervals.values():
            if len(intervals) > 1:
                # 抖动 = 间隔的标准差 (秒)
                jitter = np.std(list(intervals))
                total_jitter += jitter
                count += 1
        
        avg_jitter_ms = (total_jitter / count * 1000) if count > 0 else 0.0
        
        # 评分逻辑: <5ms优秀(1.0), <15ms良好(0.8), <30ms警告(0.5), >30ms差(0.2)
        if avg_jitter_ms < 5: score = 1.0
        elif avg_jitter_ms < 15: score = 0.8
        elif avg_jitter_ms < 30: score = 0.5
        else: score = 0.2

        return {
            "communication": {
                "jitter_ms": round(avg_jitter_ms, 2),
                "packet_rate_Hz": sum(len(q) for q in self.packet_intervals.values()) / 5.0, # 粗略估算最近50个包的频率
                "packet_total": sum(self.packet_count.values()),
                "score": score,
                "status": "normal" if score > 0.6 else "warning"
            }
        }
    
    # ---------------------------------------------------------
    # 维度 1: 算力资源 (Computing)
    # ---------------------------------------------------------
    def _calc_computing_resources(self, data: dict) -> Dict[str, Any]:
        """计算算力资源指标"""
        # 优先使用真实数据
        cpu = data.get('cpu_load', None)
        mem = data.get('mem_usage', None)

        if cpu is not None:
             self.cpu_readings.append(cpu)
        if mem is not None:
             self.mem_readings.append(mem)

        # 获取当前值（平滑处理）
        curr_cpu = np.mean(self.cpu_readings) if self.cpu_readings else 20.0 # 默认20
        curr_mem = np.mean(self.mem_readings) if self.mem_readings else 40.0
        
        # 评分: CPU > 90% 0分, < 20% 1分 (线性插值)
        # Resource Score (Ci) = 1 - Peak_CPU (normalized)
        score = max(0.0, min(1.0, 1.0 - (curr_cpu - 20) / 80.0))
        
        return {
            "computing": {
                "cpu_load": round(curr_cpu, 1),
                "memory_usage": round(curr_mem, 1),
                "score": round(score, 2),
                "status": "normal" if curr_cpu < 80 else "high"
            }
        }
    
    # ---------------------------------------------------------
    # 维度 2: 通信资源 (已由 _get_comm_summary 替代具体计算)
    # ---------------------------------------------------------
    def _calc_communication(self, data: dict) -> Dict[str, Any]:
        """保留接口兼容性"""
        return self._get_comm_summary()
    
    # ---------------------------------------------------------
    # 维度 3: 能耗指标 (Energy)
    # ---------------------------------------------------------
    def _calc_energy(self, data: dict) -> Dict[str, Any]:
        """计算能耗指标"""
        # 尝试获取真实电压/电流
        # fcs_states 中可能包含 battery_voltage, battery_current
        # 或者 data['data'] 中包含
        payload = data.get('data', data)
        
        voltage = payload.get('battery_voltage', payload.get('voltage', 24.0)) # 默认24V
        current = payload.get('battery_current', payload.get('current', 10.0)) # 默认10A
        
        # 1. 瞬时功率
        power = voltage * current
        
        # 2. 累计能耗 (积分)
        now = time.time()
        dt = now - self.last_energy_time
        if dt < 5.0 and dt > 0:  # 防止时间跳变太大 (如重连)
            self.total_energy += power * dt
        self.last_energy_time = now
        
        # 更新功率读数
        self.power_readings.append(power)
        avg_power = np.mean(self.power_readings) if self.power_readings else power
        
        # 3. 计算评分（假设额定功率 1000W）
        # 低功耗得分高
        norm_power = min(1.0, avg_power / 1000.0)
        score = 1.0 - norm_power
        
        return {
            "energy": {
                "power_watts": round(power, 1),
                "power_avg": round(avg_power, 1),
                "total_joules": round(self.total_energy, 1), # J
                "voltage_v": round(voltage, 1),
                "current_a": round(current, 1),
                "score": round(score, 2),
                "status": "normal" if score > 0.4 else "warning"
            }
        }
    
    # ---------------------------------------------------------
    # 维度 4: 任务效能 (Mission Efficacy)
    # ---------------------------------------------------------
    def _calc_mission(self, data: dict) -> Dict[str, Any]:
        """计算任务效能指标"""
        # 从 planning_telemetry 获取航点信息
        payload = data.get('data', data)
        
        current_wp = payload.get('current_waypoint_index', self.current_waypoint)
        total_wp = payload.get('total_waypoints', self.waypoint_count)
        
        if total_wp > 0: self.waypoint_count = total_wp
        self.current_waypoint = current_wp
        
        # 1. 任务覆盖率
        coverage = current_wp / total_wp if total_wp > 0 else 0
        
        # 2. 安全余量 (Safety Margin) -> Sj
        # 定义为: (当前电量 - 返航所需电量) / 总电量 
        # 或者: min(采样时刻的安全性余量) - 这里简化为电量与距离的函数
        battery_level = payload.get('battery_level', 100.0) # %
        dist_to_home = payload.get('dist_to_home', 0.0) # meters
        
        # 假设每100m消耗1%电量，且保留20%余量
        needed_batt = (dist_to_home / 100.0) * 1.0 + 20.0 
        margin = battery_level - needed_batt 
        
        self.safety_margins.append(margin)
        avg_margin = np.mean(self.safety_margins)
        
        # 评分: margin > 20% -> 1.0, < 0% -> 0.0
        safety_score = max(0.0, min(1.0, (avg_margin) / 20.0))
        
        mission_score = (coverage * 0.4 + safety_score * 0.6)
        
        return {
            "mission": {
                "progress_percent": round(coverage * 100, 1),
                "current_waypoint": current_wp,
                "total_waypoints": total_wp,
                "safety_margin": round(avg_margin, 1),
                "score": round(mission_score, 2),
                "status": "normal" if safety_score > 0.5 else "critical"
            }
        }
    
    # ---------------------------------------------------------
    # 维度 5: 飞行性能 (Flight Performance)
    # ---------------------------------------------------------
    def _calc_flight_performance(self, data: dict) -> Dict[str, Any]:
        """计算飞行性能指标"""
        telemetry = data.get('data', {})
        
        # 获取实际值与指令值
        # 注意: 需确保协议中有对应的 cmd_ 字段
        pos_n = telemetry.get('pos_n', 0)
        pos_e = telemetry.get('pos_e', 0)
        pos_d = telemetry.get('pos_d', 0)
        
        cmd_n = telemetry.get('cmd_pos_n', pos_n) # 如果没有cmd，默认无误差
        cmd_e = telemetry.get('cmd_pos_e', pos_e)
        cmd_d = telemetry.get('cmd_pos_d', pos_d)
        
        # 1. 轨迹跟踪误差 (MSE/RMSE)
        err_n = pos_n - cmd_n
        err_e = pos_e - cmd_e
        err_d = pos_d - cmd_d
        
        error_distance = math.sqrt(err_n**2 + err_e**2 + err_d**2)
        
        self.rmse_window.append(error_distance)
        self.trajectory_errors.append(error_distance)
        
        avg_rmse = np.mean(self.rmse_window) if self.rmse_window else 0
        
        # 2. 响应性 (Responsiveness) -> Rj
        # 理想情况下计算: 1 / 关键指令平均延迟
        # 这里用误差反比作为响应性的代理 (误差小说明响应快)
        # Score = 1 - (RMSE / Limit), Limit 设为 5米
        limit_rmse = 5.0
        score = max(0.0, 1.0 - (avg_rmse / limit_rmse))
        
        return {
            "performance": {
                "rmse_meters": round(avg_rmse, 3),
                "position_error_m": round(error_distance, 3),
                "score": round(score, 2),
                "status": "excellent" if score > 0.8 else ("good" if score > 0.5 else "poor")
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