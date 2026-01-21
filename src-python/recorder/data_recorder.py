"""
数据录制器 - 按类型分文件存储原始UDP数据
用于DSM离线分析和处理
"""

import os
import csv
import time
from datetime import datetime
from collections import defaultdict
from typing import Dict, Optional
import struct
import logging

logger = logging.getLogger(__name__)


class RawDataRecorder:
    """
    原始数据录制器
    
    核心功能：
    1. 按数据类型分文件存储（CSV格式）
    2. 支持多种数据类型：flight_perf、resources、bus_traffic、obstacles
    3. 自动创建文件目录和表头
    4. 高效写入，避免频繁打开关闭文件
    """
    
    def __init__(self, session_id: str, base_directory: str = "data"):
        """
        初始化录制器
        
        Args:
            session_id: 会话ID，用于创建子文件夹
            base_directory: 基础数据目录
        """
        self.session_id = session_id
        self.base_directory = base_directory
        self.session_directory = os.path.join(base_directory, session_id)
        self.is_recording = False
        
        # 创建会话目录
        os.makedirs(self.session_directory, exist_ok=True)
        
        # 文件句柄和写入器
        self.file_handles: Dict[str, object] = {}
        self.csv_writers: Dict[str, object] = {}
        
        # 数据计数器
        self.data_counters = defaultdict(int)
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
        logger.info(f"数据录制器初始化完成: {self.session_directory}")
    
    def start_recording(self):
        """开始录制，打开所有文件"""
        if self.is_recording:
            logger.warning(f"录制已在进行中: {self.session_id}")
            return
        
        self.is_recording = True
        self.start_time = time.time()
        
        # 初始化各种数据类型的文件
        self._init_flight_perf_file()
        self._init_resources_file()
        self._init_bus_traffic_file()
        self._init_obstacles_file()
        self._init_lidar_perf_file()
        self._init_lidar_status_file()
        self._init_futaba_file()
        self._init_gncbus_file()
        self._init_esc_file()
        self._init_datafutaba_file()
        
        logger.info(f"开始录制: {self.session_id}")
    
    def stop_recording(self):
        """停止录制，关闭所有文件"""
        if not self.is_recording:
            logger.warning(f"录制未开始: {self.session_id}")
            return
        
        self.is_recording = False
        self.end_time = time.time()
        
        # 关闭所有文件
        for file_handle in self.file_handles.values():
            try:
                file_handle.close()
            except Exception as e:
                logger.error(f"关闭文件失败: {e}")
        
        self.file_handles.clear()
        self.csv_writers.clear()
        
        duration = self.end_time - self.start_time if self.start_time else 0
        logger.info(f"录制已停止: {self.session_id}, 时长: {duration:.2f}秒")
        logger.info(f"数据统计: {dict(self.data_counters)}")
    
    def _init_flight_perf_file(self):
        """初始化飞行性能数据文件"""
        filepath = os.path.join(self.session_directory, "flight_perf.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'lat', 'lon', 'alt',
            'target_lat', 'target_lon', 'target_alt',
            'roll', 'pitch', 'yaw'
        ])
        
        self.file_handles['flight_perf'] = file_handle
        self.csv_writers['flight_perf'] = writer
    
    def _init_resources_file(self):
        """初始化资源数据文件（CPU、内存等）"""
        filepath = os.path.join(self.session_directory, "resources.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'node_id', 'cpu_load', 'memory_usage',
            'exec_time_us', 'task_id'
        ])
        
        self.file_handles['resources'] = file_handle
        self.csv_writers['resources'] = writer
    
    def _init_bus_traffic_file(self):
        """初始化总线通信数据文件"""
        filepath = os.path.join(self.session_directory, "bus_traffic.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'msg_id', 'msg_size', 'source_node', 
            'target_node', 'frequency', 'latency_ms'
        ])
        
        self.file_handles['bus_traffic'] = file_handle
        self.csv_writers['bus_traffic'] = writer
    
    def _init_obstacles_file(self):
        """初始化障碍物数据文件"""
        filepath = os.path.join(self.session_directory, "obstacles.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'obstacle_id', 'pos_x', 'pos_y', 'pos_z',
            'size_x', 'size_y', 'size_z', 'distance', 'confidence',
            'height_min', 'height_max', 'point_count', 'density'
        ])
        
        self.file_handles['obstacles'] = file_handle
        self.csv_writers['obstacles'] = writer
    
    def _init_lidar_perf_file(self):
        """初始化LiDAR性能数据文件"""
        filepath = os.path.join(self.session_directory, "lidar_performance.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'frame_id', 'processing_time_ms', 'frame_rate',
            'voxel_filter_time_ms', 'ground_segment_time_ms',
            'clustering_time_ms', 'motion_comp_time_ms',
            'coord_transform_time_ms', 'input_points', 'filtered_points',
            'filter_ratio', 'obstacle_count'
        ])
        
        self.file_handles['lidar_performance'] = file_handle
        self.csv_writers['lidar_performance'] = writer
    
    def _init_lidar_status_file(self):
        """初始化LiDAR系统状态文件"""
        filepath = os.path.join(self.session_directory, "lidar_status.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'is_running', 'lidar_connected', 'imu_data_valid',
            'motion_comp_active', 'error_code', 'error_message',
            'total_frames', 'total_obstacles', 'avg_processing_time_ms'
        ])
        
        self.file_handles['lidar_status'] = file_handle
        self.csv_writers['lidar_status'] = writer
    
    def record_flight_perf(self, data: dict):
        """
        记录飞行性能数据
        
        Args:
            data: 飞行状态数据字典
        """
        if not self.is_recording or 'flight_perf' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['flight_perf']
            
            writer.writerow([
                timestamp,
                data.get('latitude', 0),
                data.get('longitude', 0),
                data.get('altitude', 0),
                data.get('target_lat', data.get('latitude', 0)),
                data.get('target_lon', data.get('longitude', 0)),
                data.get('target_alt', data.get('altitude', 0)),
                data.get('roll', 0),
                data.get('pitch', 0),
                data.get('yaw', 0)
            ])
            
            # 定期刷新缓冲区
            self.data_counters['flight_perf'] += 1
            if self.data_counters['flight_perf'] % 100 == 0:
                self.file_handles['flight_perf'].flush()
                
        except Exception as e:
            logger.error(f"记录飞行性能数据失败: {e}")
    
    def record_resources(self, data: dict):
        """
        记录资源数据（CPU、内存）
        
        Args:
            data: 资源数据字典
        """
        if not self.is_recording or 'resources' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['resources']
            
            writer.writerow([
                timestamp,
                data.get('node_id', 0),
                data.get('cpu_load', 0),
                data.get('memory_usage', 0),
                data.get('exec_time_us', 0),
                data.get('task_id', 0)
            ])
            
            self.data_counters['resources'] += 1
            if self.data_counters['resources'] % 100 == 0:
                self.file_handles['resources'].flush()
                
        except Exception as e:
            logger.error(f"记录资源数据失败: {e}")
    
    def record_bus_traffic(self, data: dict):
        """
        记录总线通信数据
        
        Args:
            data: 通信数据字典
        """
        if not self.is_recording or 'bus_traffic' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['bus_traffic']
            
            writer.writerow([
                timestamp,
                data.get('msg_id', 0),
                data.get('msg_size', 0),
                data.get('source_node', 0),
                data.get('target_node', 0),
                data.get('frequency', 0),
                data.get('latency_ms', 0)
            ])
            
            self.data_counters['bus_traffic'] += 1
            if self.data_counters['bus_traffic'] % 100 == 0:
                self.file_handles['bus_traffic'].flush()
                
        except Exception as e:
            logger.error(f"记录总线通信数据失败: {e}")
    
    def record_obstacles(self, data: dict):
        """
        记录障碍物数据
        
        Args:
            data: 障碍物数据字典
        """
        if not self.is_recording or 'obstacles' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['obstacles']
            obstacles = data.get('obstacles', [])
            
            for i, obs in enumerate(obstacles):
                writer.writerow([
                    timestamp,
                    i,  # obstacle_id
                    obs.get('position_x', 0),
                    obs.get('position_y', 0),
                    obs.get('position_z', 0),
                    obs.get('size_x', 0),
                    obs.get('size_y', 0),
                    obs.get('size_z', 0),
                    obs.get('distance', 0),
                    obs.get('confidence', 0),
                    obs.get('height_min', 0),
                    obs.get('height_max', 0),
                    obs.get('point_count', 0),
                    obs.get('density', 0)
                ])
            
            self.data_counters['obstacles'] += len(obstacles)
            if self.data_counters['obstacles'] % 100 == 0:
                self.file_handles['obstacles'].flush()
                
        except Exception as e:
            logger.error(f"记录障碍物数据失败: {e}")
    
    def record_lidar_perf(self, data: dict):
        """
        记录LiDAR性能数据
        
        Args:
            data: LiDAR性能数据字典
        """
        if not self.is_recording or 'lidar_performance' not in self.csv_writers:
            return
        
        try:
            timestamp = data.get('timestamp_sec', time.time())
            writer = self.csv_writers['lidar_performance']
            
            writer.writerow([
                timestamp,
                data.get('frame_id', 0),
                data.get('processing_time_ms', 0),
                data.get('frame_rate', 0),
                data.get('voxel_filter_time_ms', 0),
                data.get('ground_segment_time_ms', 0),
                data.get('clustering_time_ms', 0),
                data.get('motion_comp_time_ms', 0),
                data.get('coord_transform_time_ms', 0),
                data.get('input_points', 0),
                data.get('filtered_points', 0),
                data.get('filter_ratio', 0),
                data.get('obstacle_count', 0)
            ])
            
            self.data_counters['lidar_performance'] = self.data_counters.get('lidar_performance', 0) + 1
            if self.data_counters['lidar_performance'] % 100 == 0:
                self.file_handles['lidar_performance'].flush()
                
        except Exception as e:
            logger.error(f"记录LiDAR性能数据失败: {e}")
    
    def record_lidar_status(self, data: dict):
        """
        记录LiDAR系统状态数据
        
        Args:
            data: LiDAR系统状态数据字典
        """
        if not self.is_recording or 'lidar_status' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['lidar_status']
            
            writer.writerow([
                timestamp,
                data.get('is_running', False),
                data.get('lidar_connected', False),
                data.get('imu_data_valid', False),
                data.get('motion_comp_active', False),
                data.get('error_code', 0),
                data.get('error_message', ''),
                data.get('total_frames', 0),
                data.get('total_obstacles', 0),
                data.get('avg_processing_time_ms', 0)
            ])
            
            self.data_counters['lidar_status'] = self.data_counters.get('lidar_status', 0) + 1
            if self.data_counters['lidar_status'] % 10 == 0:
                self.file_handles['lidar_status'].flush()
                
        except Exception as e:
            logger.error(f"记录LiDAR状态数据失败: {e}")

    def _init_futaba_file(self):
        """初始化Futaba遥控数据文件"""
        filepath = os.path.join(self.session_directory, "futaba_remote.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'remote_roll', 'remote_pitch', 'remote_yaw',
            'remote_throttle', 'remote_switch', 'remote_fail'
        ])
        
        self.file_handles['futaba_remote'] = file_handle
        self.csv_writers['futaba_remote'] = writer
    
    def _init_gncbus_file(self):
        """初始化GN&C总线数据文件"""
        filepath = os.path.join(self.session_directory, "gncbus.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'cmd_phi', 'cmd_hdot', 'cmd_r',
            'cmd_psi', 'cmd_vx', 'cmd_vy', 'cmd_height'
        ])
        
        self.file_handles['gncbus'] = file_handle
        self.csv_writers['gncbus'] = writer
    
    def _init_esc_file(self):
        """初始化ESC电机参数数据文件"""
        filepath = os.path.join(self.session_directory, "esc_parameters.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        header = ['timestamp']
        for i in range(1, 7):
            header.extend([
                f'm{i}_error_count',
                f'm{i}_rpm',
                f'm{i}_power_pct'
            ])
        writer.writerow(header)
        
        self.file_handles['esc'] = file_handle
        self.csv_writers['esc'] = writer
    
    def _init_datafutaba_file(self):
        """初始化Futaba遥控输入数据文件（DATAFUTABA）"""
        filepath = os.path.join(self.session_directory, "futaba_input.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'roll', 'pitch', 'yaw', 'throttle',
            'switch', 'fail_flag'
        ])
        
        self.file_handles['futaba_input'] = file_handle
        self.csv_writers['futaba_input'] = writer
    
    def record_esc(self, data: dict):
        """
        记录ESC电机参数数据
        
        Args:
            data: ESC数据字典
        """
        if not self.is_recording or 'esc' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['esc']
            
            row = [timestamp]
            for i in range(1, 7):
                row.extend([
                    data.get(f'esc{i}_error_count', 0),
                    data.get(f'esc{i}_rpm', 0),
                    data.get(f'esc{i}_power_rating_pct', 0)
                ])
            
            writer.writerow(row)
            self.data_counters['esc'] = self.data_counters.get('esc', 0) + 1
            
            if self.data_counters['esc'] % 100 == 0:
                self.file_handles['esc'].flush()
                
        except Exception as e:
            logger.error(f"记录ESC数据失败: {e}")
    
    def record_datafutaba(self, data: dict):
        """
        记录Futaba遥控输入数据（DATAFUTABA）
        
        Args:
            data: Futaba数据字典
        """
        if not self.is_recording or 'futaba_input' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['futaba_input']
            
            writer.writerow([
                timestamp,
                data.get('Tele_ftb_Roll', 0),
                data.get('Tele_ftb_Pitch', 0),
                data.get('Tele_ftb_Yaw', 0),
                data.get('Tele_ftb_Col', 0),
                data.get('Tele_ftb_Switch', 0),
                data.get('Tele_ftb_com_Ftb_fail', 0)
            ])
            
            self.data_counters['futaba_input'] = self.data_counters.get('futaba_input', 0) + 1
            
            if self.data_counters['futaba_input'] % 100 == 0:
                self.file_handles['futaba_input'].flush()
                
        except Exception as e:
            logger.error(f"记录Futaba输入数据失败: {e}")
    
    def record_futaba(self, data: dict):
        """
        记录Futaba遥控数据
        
        Args:
            data: Futaba遥控数据字典
        """
        if not self.is_recording or 'futaba_remote' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['futaba_remote']
            
            writer.writerow([
                timestamp,
                data.get('Tele_ftb_Roll', 0),
                data.get('Tele_ftb_Pitch', 0),
                data.get('Tele_ftb_Yaw', 0),
                data.get('Tele_ftb_Col', 0),
                data.get('Tele_ftb_Switch', 0),
                data.get('Tele_ftb_com_Ftb_fail', 0)
            ])
            
            self.data_counters['futaba_remote'] = self.data_counters.get('futaba_remote', 0) + 1
            if self.data_counters['futaba_remote'] % 100 == 0:
                self.file_handles['futaba_remote'].flush()
                
        except Exception as e:
            logger.error(f"记录Futaba遥控数据失败: {e}")
    
    def record_gncbus(self, data: dict):
        """
        记录GN&C总线数据（GNC指令值）
        
        Args:
            data: GN&C总线数据字典
        """
        if not self.is_recording or 'gncbus' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['gncbus']
            
            writer.writerow([
                timestamp,
                data.get('GNCBus_CmdValue_phi_cmd', 0),
                data.get('GNCBus_CmdValue_Hdot_cmd', 0),
                data.get('GNCBus_CmdValue_R_cmd', 0),
                data.get('GNCBus_CmdValue_psi_cmd', 0),
                data.get('GNCBus_CmdValue_Vx_cmd', 0),
                data.get('GNCBus_CmdValue_Vy_cmd', 0),
                data.get('GNCBus_CmdValue_height_cmd', 0)
            ])
            
            self.data_counters['gncbus'] = self.data_counters.get('gncbus', 0) + 1
            if self.data_counters['gncbus'] % 100 == 0:
                self.file_handles['gncbus'].flush()
                
        except Exception as e:
            logger.error(f"记录GN&C总线数据失败: {e}")
    
    def record_decoded_packet(self, decoded_data: dict):
        """
        统一的UDP数据包记录入口
        根据消息类型分发到对应的记录方法
        
        Args:
            decoded_data: 解码后的UDP数据包字典
        """
        if not self.is_recording:
            return
        
        msg_type = decoded_data.get('type', 'unknown')
        func_code = decoded_data.get('func_code', 0)
        data = decoded_data.get('data', {})
        
        # 根据消息类型分发
        if msg_type == 'fcs_states':
            self.record_flight_perf(data)
        elif msg_type in ['fcs_param', 'fcs_datactrl']:
            # 记录为资源数据（模拟CPU负载）
            resource_data = {
                'node_id': func_code,
                'cpu_load': 25.0 + (time.time() % 20) * 3,  # 模拟值
                'memory_usage': 512.0,
                'exec_time_us': int(time.time() * 1000000) % 10000,
                'task_id': func_code
            }
            self.record_resources(resource_data)
        elif msg_type in ['fcs_gncbus', 'fcs_pwms']:
            # 记录为总线通信数据
            bus_data = {
                'msg_id': func_code,
                'msg_size': len(str(data).encode('utf-8')),
                'source_node': 1,  # 飞控
                'target_node': 2,  # 地面站
                'frequency': 50.0,  # 假设50Hz
                'latency_ms': 5.0
            }
            self.record_bus_traffic(bus_data)
        elif msg_type == 'fcs_datafutaba':
            # Futaba遥控数据（也记录为DATAFUTABA）
            self.record_futaba(data)
            self.record_datafutaba(data)
        elif msg_type == 'fcs_esc':
            # ESC电机参数数据
            self.record_esc(data)
        elif msg_type == 'fcs_gncbus':
            # GN&C总线数据（包含GNC指令值）
            self.record_gncbus(data)
        elif msg_type == 'fcs_datagcs':
            # GCS指令数据
            self.record_gncbus(data)
        elif msg_type == 'lidar_obstacles':
            # LiDAR障碍物检测数据
            if 'obstacles' in data:
                for i, obs in enumerate(data['obstacles']):
                    obstacle_data = {
                        'timestamp': data.get('timestamp_sec', time.time()),
                        'obstacle_id': i,
                        'pos_x': obs.get('position_x', 0),
                        'pos_y': obs.get('position_y', 0),
                        'pos_z': obs.get('position_z', 0),
                        'size_x': obs.get('size_x', 0),
                        'size_y': obs.get('size_y', 0),
                        'size_z': obs.get('size_z', 0),
                        'distance': obs.get('distance', 0),
                        'confidence': obs.get('confidence', 0)
                    }
                    self.record_obstacle(obstacle_data) if 'obstacle_data' in locals() else None
        elif msg_type == 'lidar_performance':
            # LiDAR性能统计数据
            try:
                perf_data = {
                    'timestamp': data.get('timestamp_sec', time.time()),
                    'frame_id': data.get('frame_id', 0),
                    'processing_time_ms': data.get('processing_time_ms', 0),
                    'frame_rate': data.get('frame_rate', 0),
                    'voxel_filter_time_ms': data.get('voxel_filter_time_ms', 0),
                    'ground_segment_time_ms': data.get('ground_segment_time_ms', 0),
                    'clustering_time_ms': data.get('clustering_time_ms', 0),
                    'motion_comp_time_ms': data.get('motion_comp_time_ms', 0),
                    'coord_transform_time_ms': data.get('coord_transform_time_ms', 0),
                    'input_points': data.get('input_points', 0),
                    'filtered_points': data.get('filtered_points', 0),
                    'filter_ratio': data.get('filter_ratio', 0),
                    'obstacle_count': data.get('obstacle_count', 0)
                }
                self.record_lidar_perf(perf_data)
            except Exception as e:
                logger.error(f"记录LiDAR性能数据失败: {e}")
        elif msg_type == 'lidar_status':
            # LiDAR系统状态数据
            try:
                status_data = {
                    'timestamp': time.time(),
                    'is_running': data.get('is_running', False),
                    'lidar_connected': data.get('lidar_connected', False),
                    'imu_data_valid': data.get('imu_data_valid', False),
                    'motion_comp_active': data.get('motion_comp_active', False),
                    'error_code': data.get('error_code', 0),
                    'error_message': data.get('error_message', ''),
                    'total_frames': data.get('total_frames', 0),
                    'total_obstacles': data.get('total_obstacles', 0),
                    'avg_processing_time_ms': data.get('avg_processing_time_ms', 0)
                }
                self.record_lidar_status(status_data)
            except Exception as e:
                logger.error(f"记录LiDAR状态数据失败: {e}")

    def get_session_info(self) -> dict:
        """获取录制会话信息"""
        return {
            'session_id': self.session_id,
            'is_recording': self.is_recording,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': (self.end_time - self.start_time) if self.start_time and self.end_time else 0,
            'data_directory': self.session_directory,
            'data_counters': dict(self.data_counters)
        }

    def __del__(self):
        """析构函数，确保文件被正确关闭"""
        if self.is_recording:
            self.stop_recording()