"""
CSV 数据记录器 - 分类记录 (FCS, Planning, Radar)
"""

import os
import csv
import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class UnifiedRecorder:
    def __init__(self, session_dir: str):
        self.session_dir = session_dir
        self.files = {}
        self.writers = {}
        self.counters = {}

    def init_files(self):
        """初始化三个主要的CSV文件"""
        # 1. 飞控数据 (FCS)
        self._init_fcs_file()
        
        # 2. 规划数据 (Planning)
        self._init_planning_file()
        
        # 3. 雷达数据 (Radar)
        self._init_radar_file()
        
    def _init_fcs_file(self):
        """初始化飞控遥测文件 (使用 csv_helper_full 的宽表头)"""
        path = os.path.join(self.session_dir, "fcs_telemetry.csv")
        f = open(path, 'w', newline='', encoding='utf-8')
        from . import csv_helper_full
        f.write(csv_helper_full.get_full_header() + "\n")
        self.files['fcs'] = f
        self.counters['fcs'] = 0

    def _init_planning_file(self):
        """初始化规划数据文件 (GCSTelemetry_T)"""
        path = os.path.join(self.session_dir, "planning_telemetry.csv")
        f = open(path, 'w', newline='', encoding='utf-8')
        writer = csv.writer(f)
        
        # 定义表头 (基于 GCSTelemetry_T)
        headers = [
            "timestamp_local", "seq_id", "timestamp_remote", 
            "pos_x", "pos_y", "pos_z", "vel", "update_flags", "status",
            "global_path_count", "local_traj_count", "obstacle_count",
            "global_path_preview", "local_path_preview" # 简要信息
        ]
        writer.writerow(headers)
        
        self.files['planning'] = f
        self.writers['planning'] = writer
        self.counters['planning'] = 0

    def _init_radar_file(self):
        """初始化雷达数据文件 (Obstacles, Perf, Status)"""
        path = os.path.join(self.session_dir, "radar_data.csv")
        f = open(path, 'w', newline='', encoding='utf-8')
        writer = csv.writer(f)
        
        # 定义表头 (聚合 radar 信息)
        headers = [
            "timestamp_local", "type", 
            # Obstacles Summary
            "obs_count", "obs_frame_id", "obs_timestamp_sec",
            # Performance
            "perf_proc_time", "perf_fps", "perf_points_in", "perf_points_out",
            # Status
            "status_running", "status_connected", "status_error_code"
        ]
        writer.writerow(headers)
        
        self.files['radar'] = f
        self.writers['radar'] = writer
        self.counters['radar'] = 0

    def _flush_if_needed(self, key):
        self.counters[key] += 1
        if self.counters[key] % 50 == 0:
            self.files[key].flush()

    def record_fcs(self, msg_type: str, data: dict):
        if 'fcs' not in self.files: return
        try:
            from . import csv_helper_full
            # 包装一下以符合 csv_helper_full 接口
            wrapped = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                'data': data
            }
            # 利用 helper 获取宽表行
            # 注意: csv_helper_full 是针对 ExtY_FCS_T 结构的
            # 如果是具体子类型 (如 fcs_states), helper 会把其他列留空
            line = csv_helper_full.get_data_for_type(msg_type, wrapped)
            self.files['fcs'].write(line + "\n")
            self._flush_if_needed('fcs')
        except Exception as e:
            logger.error(f"FCS record error: {e}")

    def record_planning(self, data: dict):
        if 'planning' not in self.writers: return
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            # 提取 global_path / local_path 的预览 (前1-2个点)
            gp = data.get('global_path', [])
            lp = data.get('local_path', [])
            gp_preview = f"len={len(gp)}" + (f" p0={gp[0]}" if gp else "")
            lp_preview = f"len={len(lp)}" + (f" p0={lp[0]}" if lp else "")

            row = [
                ts,
                data.get('seq_id', 0),
                data.get('timestamp', 0),
                f"{data.get('current_pos_x', 0):.4f}",
                f"{data.get('current_pos_y', 0):.4f}",
                f"{data.get('current_pos_z', 0):.4f}",
                f"{data.get('current_vel', 0):.4f}",
                data.get('update_flags', 0),
                data.get('status', 0),
                data.get('global_path_count', 0),
                data.get('local_traj_count', 0),
                data.get('obstacle_count', 0),
                gp_preview,
                lp_preview
            ]
            self.writers['planning'].writerow(row)
            self._flush_if_needed('planning')
        except Exception as e:
            logger.error(f"Planning record error: {e}")

    def record_radar(self, msg_type: str, data: dict):
        if 'radar' not in self.writers: return
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            row = [ts, msg_type] + [""] * 10 # 预填充

            if msg_type == 'lidar_obstacles':
                # obs_count, frame_id, timestamp
                row[2] = data.get('obstacle_count', 0)
                row[3] = data.get('frame_id', 0)
                row[4] = f"{data.get('timestamp_sec', 0):.4f}"
            
            elif msg_type == 'lidar_performance':
                # perf_proc_time, fps, points_in, points_out
                row[5] = f"{data.get('processing_time_ms', 0):.2f}"
                row[6] = f"{data.get('frame_rate', 0):.2f}"
                row[7] = data.get('input_points', 0)
                row[8] = data.get('filtered_points', 0)

            elif msg_type == 'lidar_status':
                # running, connected, error
                row[9] = 1 if data.get('is_running') else 0
                row[10] = 1 if data.get('lidar_connected') else 0
                row[11] = data.get('error_code', 0)
            
            self.writers['radar'].writerow(row)
            self._flush_if_needed('radar')
        except Exception as e:
            logger.error(f"Radar record error: {e}")

    def close(self):
        for f in self.files.values():
            try:
                f.close()
            except: pass
