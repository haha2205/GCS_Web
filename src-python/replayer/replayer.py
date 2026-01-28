"""
数据回放引擎
读取 CSV 文件并按时间间隔通过 WebSocket 推送数据
"""

import asyncio
import pandas as pd
import os
import logging
import time
from typing import Optional, Dict, Any
from datetime import timedelta
from websocket.websocket_manager import manager
from calculator.realtime_calculator import RealTimeCalculator

logger = logging.getLogger(__name__)


class Replayer:
    """
    数据回放引擎
    
    核心功能：
    1. 读取 CSV 文件并解析数据
    2. 按照原始时间间隔回放数据
    3. 支持播放、暂停、倍速、跳转等控制
    4. 通过 WebSocket 广播数据，伪造实时数据流
    5. 计算并发送KPI指标
    """
    
    def __init__(self, broadcast_callback=None):
        """
        初始化回放引擎
        
        Args:
            broadcast_callback: WebSocket 广播回调函数（可选）
        """
        self.df = None
        self.is_playing = False
        self.current_idx = 0
        self.speed = 1.0
        self.broadcast = broadcast_callback or manager.broadcast  # 传入WS发送函数
        self.replay_task = None
        self.total_rows = 0
        self.total_time = 0.0
        
        # KPI计算器（用于回放时计算KPI指标）
        self.calculator = RealTimeCalculator()
        
    def load_file(self, filepath: str) -> float:
        """
        加载回放文件
        
        Args:
            filepath: CSV 文件路径
            
        Returns:
            总时长（秒）
        """
        try:
            logger.info(f"加载回放文件: {filepath}")
            
            # 读取 CSV 文件，使用 on_bad_lines='skip' 跳过坏行
            # 使用 low_memory=False 优化内存使用
            self.df = pd.read_csv(filepath, low_memory=False, on_bad_lines='skip')
            self.total_rows = len(self.df)
            self.current_idx = 0
            self.is_playing = False
            
            # 确保有 rel_time 字段
            if 'rel_time' not in self.df.columns:
                # 如果没有，根据 timestamp 计算
                if 'timestamp' in self.df.columns:
                    try:
                        # 尝试解析 timestamp
                        timestamps = pd.to_datetime(self.df['timestamp'], errors='coerce')
                        self.df['rel_time'] = (timestamps - timestamps.iloc[0]).dt.total_seconds().fillna(range(len(self.df)))
                    except Exception:
                        self.df['rel_time'] = range(len(self.df))
                else:
                    self.df['rel_time'] = range(len(self.df))
            
            # 计算总时长（使用 rel_time 字段）
            self.total_time = float(self.df['rel_time'].iloc[-1])
            logger.info(f"回放文件加载成功: {self.total_rows} 行数据, {len(self.df.columns)} 列, 总时长: {self.total_time:.2f}秒")
            return self.total_time
            
        except Exception as e:
            logger.error(f"加载回放文件失败: {e}")
            raise
    
    def get_data_list(self) -> list:
        """
        获取所有可用的回放文件列表
        
        Returns:
            文件列表，每个文件包含 name, path, size, date 信息
        """
        files = []
        
        # 检查 Log 目录（根据项目结构，日志在Log目录）
        log_dir = 'Log'
        if os.path.exists(log_dir):
            for filename in os.listdir(log_dir):
                if filename.endswith('.csv'):
                    filepath = os.path.join(log_dir, filename)
                    stat = os.stat(filepath)
                    files.append({
                        'name': filename,
                        'path': filepath,
                        'size': stat.st_size,
                        'date': stat.st_mtime
                    })
        
        # 检查 records 目录（兼容性）
        records_dir = 'records'
        if os.path.exists(records_dir):
            for filename in os.listdir(records_dir):
                if filename.endswith('.csv'):
                    filepath = os.path.join(records_dir, filename)
                    # 避免重复
                    if not any(f['name'] == filename for f in files):
                        stat = os.stat(filepath)
                        files.append({
                            'name': filename,
                            'path': filepath,
                            'size': stat.st_size,
                            'date': stat.st_mtime
                        })
        
        # 按日期倒序排列
        files.sort(key=lambda x: x['date'], reverse=True)
        
        return files
    
    async def start(self):
        """启动回放循环"""
        if self.replay_task is None or self.replay_task.done():
            self.replay_task = asyncio.create_task(self._replay_loop())
            logger.info("回放循环已启动")
    
    async def stop(self):
        """停止回放"""
        self.is_playing = False
        if self.replay_task and not self.replay_task.done():
            self.replay_task.cancel()
            try:
                await self.replay_task
            except asyncio.CancelledError:
                pass
        logger.info("回放已停止")
    
    async def _replay_loop(self):
        """
        回放循环
        读取 DataFrame 并按照时间间隔推送数据
        """
        while True:
            try:
                if self.is_playing and self.df is not None and self.current_idx < self.total_rows:
                    # 1. 获取当前帧数据
                    row = self.df.iloc[self.current_idx]
                    data_dict = {}
                    
                    # 安全地将Series转换为字典，处理NaN值
                    for col in self.df.columns:
                        val = row[col]
                        # 处理NaN值
                        if pd.isna(val) or pd.isnull(val):
                            data_dict[col] = 0
                        else:
                            data_dict[col] = val
                    
                    # 2. 发送遥测数据（伪装成 UDP 数据）
                    await self._send_telemetry_data(data_dict)
                    
                    # 3. 发送回放状态更新（每10帧发送一次）
                    if self.current_idx % 10 == 0:
                        current_time = data_dict.get('rel_time', self.current_idx)
                        # 确保current_time不为NaN
                        if pd.isna(current_time) or pd.isnull(current_time):
                            current_time = self.current_idx
                        progress = (self.current_idx / self.total_rows) * 100
                        await self._send_replay_status(float(current_time), float(progress))
                    
                    # 4. 计算等待时间并推进索引
                    if self.current_idx < self.total_rows - 1:
                        current_time = data_dict.get('rel_time', self.current_idx)
                        next_time = self.df.iloc[self.current_idx + 1].get('rel_time', self.current_idx + 1)
                        
                        # 处理NaN时间值
                        if pd.isna(current_time) or pd.isnull(current_time):
                            current_time = self.current_idx
                        else:
                            current_time = float(current_time)
                        
                        if pd.isna(next_time) or pd.isnull(next_time):
                            next_time = self.current_idx + 1
                        else:
                            next_time = float(next_time)
                        
                        wait_time = (next_time - current_time) / self.speed
                        # 确保等待时间为正数
                        if wait_time > 0:
                            await asyncio.sleep(max(0.001, wait_time))
                        else:
                            await asyncio.sleep(0.01)
                    else:
                        # 到达最后一帧，停止回放
                        self.is_playing = False
                        logger.info("回放已完成")
                        await self._send_replay_status(self.total_time, 100.0)
                    
                    self.current_idx += 1
                else:
                    # 暂停或未加载文件时待机
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                logger.info("回放循环被取消")
                break
            except Exception as e:
                logger.error(f"回放循环错误: {e}", exc_info=True)
                await asyncio.sleep(0.1)
    
    async def _send_telemetry_data(self, data_dict: Dict[str, Any]):
        """
        发送遥测数据
        
        Args:
            data_dict: 数据字典
        """
        try:
            # 安全处理timestamp
            timestamp = data_dict.get('timestamp', 0)
            
            # 处理NaN的timestamp
            if pd.isna(timestamp) or pd.isnull(timestamp) or timestamp is None:
                timestamp_ms = int(time.time() * 1000)
            else:
                try:
                    # 如果是字符串格式的时间戳，转换为毫秒
                    if isinstance(timestamp, str):
                        from datetime import datetime
                        dt = datetime.strptime(timestamp.strip(), "%Y-%m-%d %H:%M:%S.%f")
                        timestamp_ms = int(dt.timestamp() * 1000)
                    else:
                        # 转为毫秒
                        timestamp_ms = int(float(timestamp) * 1000)
                except (ValueError, TypeError):
                    timestamp_ms = int(time.time() * 1000)
            
            # 构造与实时 UDP 数据相同的消息格式
            # 根据 CSV 文件中的数据类型构造消息
            message = {
                'type': 'udp_data',
                'timestamp': timestamp_ms,
                'data': self._construct_message_from_dict(data_dict)
            }
            
            await self.broadcast(message)
            
            # ===== 新增：计算并发送KPI =====
            await self._send_kpi_updates(data_dict, timestamp_ms)
            
        except Exception as e:
            logger.error(f"发送遥测数据失败: {e}", exc_info=True)
    
    async def _send_kpi_updates(self, data_dict: Dict, timestamp_ms: int):
        """计算并发送KPI更新消息
        
        Args:
            data_dict: 原始数据字典
            timestamp_ms: 时间戳（毫秒）
        """
        try:
            # 定义要处理的消息类型和对应的字段前缀
            message_configs = [
                ('fcs_states', ['states_']),
                ('fcs_pwms', ['pwm_']),
                ('fcs_datactrl', ['ctrl_', 'est_', 'ref_']),
                ('fcs_gncbus', ['GNCBus_', 'pos_', 'vel_', 'euler_']),
                ('avoiflag', ['AvoiFlag_']),
                ('fcs_datafutaba', ['Tele_ftb_']),
                ('fcs_esc', ['esc']),
                ('fcs_datagcs', ['Tele_GCS_']),
                ('fcs_param', ['param'])
            ]
            
            # 为每种消息类型计算KPI
            kpi_sent = False
            for msg_type, prefixes in message_configs:
                # 过滤出该类型的数据
                type_data = {}
                for key, value in data_dict.items():
                    for prefix in prefixes:
                        if key.startswith(prefix):
                            type_data[key] = value
                            break
                
                if type_data:
                    # 构造符合calculator输入的格式
                    calc_input = {
                        'type': msg_type,
                        'data': type_data,
                        'timestamp': timestamp_ms / 1000.0  # 转换为秒
                    }
                    
                    # 使用calculator计算KPI
                    kpi_result = self.calculator.process_packet(calc_input)
                    
                    # 发送KPI更新消息到前端
                    await manager.broadcast({
                        'type': 'kpi_update',
                        'data': kpi_result,
                        'timestamp': timestamp_ms
                    })
                    
                    kpi_sent = True
                    logger.debug(f'[Replayer] 已发送KPI更新: {msg_type}')
                    
                    # 只发送一次KPI（避免重复）
                    if kpi_sent:
                        break
            
        except Exception as e:
            logger.error(f'[Replayer] 发送KPI更新失败: {e}', exc_info=True)
    
    def _construct_message_from_dict(self, data_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        从数据字典构造消息数据
        
        Args:
            data_dict: 数据字典
            
        Returns:
            消息数据字典
        """
        # 根据 CSV 文件的内容构造不同类型的消息
        # 这里需要根据实际的 CSV 格式来构造消息
        
        # 尝试推断消息类型
        if 'states_lat' in data_dict:
            lat = float(data_dict.get('states_lat', 0))
            lon = float(data_dict.get('states_lon', 0))
            height = float(data_dict.get('states_height', 0))
            
            return {
                'type': 'fcs_states',
                'func_code': 0x01,
                'data': {
                    'latitude': lat,
                    'longitude': lon,
                    'altitude': height,
                    'states_lat': lat,
                    'states_lon': lon,
                    'states_height': height,
                    'states_Vx_GS': float(data_dict.get('states_Vx_GS', 0)),
                    'states_Vy_GS': float(data_dict.get('states_Vy_GS', 0)),
                    'states_Vz_GS': float(data_dict.get('states_Vz_GS', 0)),
                    'states_p': float(data_dict.get('states_p', 0)),
                    'states_q': float(data_dict.get('states_q', 0)),
                    'states_r': float(data_dict.get('states_r', 0)),
                    'states_phi': float(data_dict.get('states_phi', 0)),
                    'states_theta': float(data_dict.get('states_theta', 0)),
                    'states_psi': float(data_dict.get('states_psi', 0)),
                    # 姿态角（度）
                    'roll': float(data_dict.get('states_phi', 0)),
                    'pitch': float(data_dict.get('states_theta', 0)),
                    'yaw': float(data_dict.get('states_psi', 0))
                }
            }
        elif 'pwm_1' in data_dict:
            # PWM 数据
            pwms = [
                float(data_dict.get('pwm_1', 1000)),
                float(data_dict.get('pwm_2', 1000)),
                float(data_dict.get('pwm_3', 1000)),
                float(data_dict.get('pwm_4', 1000)),
                float(data_dict.get('pwm_5', 1000)),
                float(data_dict.get('pwm_6', 1000))
            ]
            
            return {
                'type': 'fcs_pwms',
                'func_code': 0x05,
                'data': {
                    'pwms': pwms
                }
            }
        elif 'Tele_ftb_Roll' in data_dict:
            # Futaba 遥控数据
            return {
                'type': 'fcs_datafutaba',
                'func_code': 0x08,
                'data': {
                    'Tele_ftb_Roll': float(data_dict.get('Tele_ftb_Roll', 0)),
                    'Tele_ftb_Pitch': float(data_dict.get('Tele_ftb_Pitch', 0)),
                    'Tele_ftb_Yaw': float(data_dict.get('Tele_ftb_Yaw', 0)),
                    'Tele_ftb_Col': float(data_dict.get('Tele_ftb_Col', 0)),
                    'Tele_ftb_Switch': int(data_dict.get('Tele_ftb_Switch', 0)),
                    'Tele_ftb_com_Ftb_fail': int(data_dict.get('Tele_ftb_com_Ftb_fail', 0))
                }
            }
        elif 'GNCBus_CmdValue_Vx_cmd' in data_dict:
            # GN&C 总线数据
            return {
                'type': 'fcs_gncbus',
                'func_code': 0x03,
                'data': {
                    'GNCBus_CmdValue_Vx_cmd': float(data_dict.get('GNCBus_CmdValue_Vx_cmd', 0)),
                    'GNCBus_CmdValue_Vy_cmd': float(data_dict.get('GNCBus_CmdValue_Vy_cmd', 0)),
                    'GNCBus_CmdValue_height_cmd': float(data_dict.get('GNCBus_CmdValue_height_cmd', 0)),
                    'GNCBus_CmdValue_psi_cmd': float(data_dict.get('GNCBus_CmdValue_psi_cmd', 0)),
                    'pos_x': float(data_dict.get('pos_x', 0)),
                    'pos_y': float(data_dict.get('pos_y', 0)),
                    'pos_z': float(data_dict.get('pos_z', 0)),
                    'vel_x': float(data_dict.get('vel_x', 0)),
                    'vel_y': float(data_dict.get('vel_y', 0)),
                    'vel_z': float(data_dict.get('vel_z', 0)),
                    'euler_phi': float(data_dict.get('euler_phi', 0)),
                    'euler_theta': float(data_dict.get('euler_theta', 0)),
                    'euler_psi': float(data_dict.get('euler_psi', 0))
                }
            }
        elif 'AvoiFlag_LaserRadar_Enabled' in data_dict:
            # 避障标志
            return {
                'type': 'avoiflag',
                'func_code': 0x09,
                'data': {
                    'AvoiFlag_LaserRadar_Enabled': bool(data_dict.get('AvoiFlag_LaserRadar_Enabled', False)),
                    'AvoiFlag_AvoidanceFlag': bool(data_dict.get('AvoiFlag_AvoidanceFlag', False)),
                    'AvoiFlag_GuideFlag': bool(data_dict.get('AvoiFlag_GuideFlag', False))
                }
            }
        else:
            # 默认：返回部分关键数据
            filtered_data = {}
            for key, value in data_dict.items():
                # 只包含一些关键字段，避免数据过大
                if any(prefix in key for prefix in ['states_', 'Tele_', 'GNCBus_', 'AvoiFlag_', 'pwm_', 'esc']):
                    filtered_data[key] = value
            
            return {
                'type': 'unknown',
                'data': filtered_data
            }
    
    async def _send_replay_status(self, current_time: float, progress: float):
        """
        发送回放状态更新
        
        Args:
            current_time: 当前时间（秒）
            progress: 进度百分比
        """
        try:
            message = {
                'type': 'replay_status',
                'timestamp': int(asyncio.get_event_loop().time() * 1000),
                'data': {
                    'current_time': current_time,
                    'progress': progress,
                    'is_playing': self.is_playing,
                    'speed': self.speed
                }
            }
            
            await self.broadcast(message)
            
        except Exception as e:
            logger.error(f"发送回放状态失败: {e}")
    
    # 控制接口
    def play(self):
        """开始播放"""
        self.is_playing = True
        logger.info("回放开始播放")
    
    def pause(self):
        """暂停播放"""
        self.is_playing = False
        logger.info("回放已暂停")
    
    def toggle_play(self):
        """切换播放/暂停"""
        if self.is_playing:
            self.pause()
        else:
            self.play()
        return self.is_playing
    
    def set_speed(self, speed: float):
        """
        设置播放速度
        
        Args:
            speed: 播放速度（例如 0.5x, 1.0x, 2.0x）
        """
        self.speed = speed
        logger.info(f"回放速度已设置为 {speed}x")
    
    def seek(self, progress_percent: float):
        """
        跳转到指定位置
        
        Args:
            progress_percent: 进度百分比 (0-100)
        """
        if self.df is None:
            logger.warning("未加载回放文件，无法跳转")
            return
        
        self.current_idx = int((progress_percent / 100) * self.total_rows)
        self.current_idx = max(0, min(self.current_idx, self.total_rows - 1))
        
        current_time = self.df.iloc[self.current_idx].get('rel_time', self.current_idx)
        logger.info(f"回放跳转到: {progress_percent:.1f}% (索引: {self.current_idx}, 时间: {current_time:.2f}秒)")
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取回放状态
        
        Returns:
            状态字典
        """
        status = {
            'is_loaded': self.df is not None,
            'is_playing': self.is_playing,
            'current_idx': self.current_idx,
            'total_rows': self.total_rows,
            'total_time': self.total_time,
            'speed': self.speed
        }
        
        if self.df is not None:
            status['progress'] = (self.current_idx / self.total_rows) * 100
            status['current_time'] = float(self.df.iloc[self.current_idx].get('rel_time', self.current_idx))
        
        return status