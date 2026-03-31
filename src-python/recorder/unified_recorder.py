"""
CSV 数据记录器 - 分类记录 (FCS, Planning, Radar)
"""

import os
import csv
import json
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
        header = csv_helper_full.get_full_header()
        f.write(header + "\n")
        self.files['fcs'] = f
        self.counters['fcs'] = 0
        # 初始化缓存
        self.fcs_cache = [""] * len(header.split(','))

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
            "global_path_json", "local_path_json", "obstacles_json" # JSON序列化的完整列表数据
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
            # Performance (含详细耗时)
            "perf_proc_time", "perf_fps", "perf_points_in", "perf_points_out",
            "perf_voxel_time", "perf_ground_time", "perf_cluster_time", # 新增详细耗时
            # Status
            "status_running", "status_connected", "status_error_code",
            # JSON Data
            "obstacles_json" # 完整障碍物列表
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
            # 利用 helper 获取数据行 (可能含有空值)
            # 注意: csv_helper_full 是针对 ExtY_FCS_T 结构的
            line = csv_helper_full.get_data_for_type(msg_type, wrapped)
            
            # 这里的逻辑是实现"最后值保持" (Zero-Order Hold)
            # 1. 拆分新数据行
            new_vals = line.split(',')
            
            # 2. 确保缓存初始化且大小匹配
            if not hasattr(self, 'fcs_cache') or self.fcs_cache is None or len(self.fcs_cache) != len(new_vals):
                self.fcs_cache = [""] * len(new_vals)
                
            # 3. 将新数据中非空的值更新到缓存中
            for i, val in enumerate(new_vals):
                if val != "":
                    self.fcs_cache[i] = val
            
            # 4. 写入完整缓存行 (不再是稀疏矩阵)
            self.files['fcs'].write(",".join(self.fcs_cache) + "\n")
            self._flush_if_needed('fcs')
        except Exception as e:
            logger.error(f"FCS record error: {e}")

    def record_planning(self, data: dict):
        if 'planning' not in self.writers: return
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            
            # 使用JSON序列化完整保留列表数据 (PathPoint_T list, Object3d_T list)
            # 假设 data 中的 global_path 等已经是 dict 或 list[dict]
            # 如果是对象实例，需要 ensure_ascii=False 并且使用 default处理器
            gp_json = json.dumps(data.get('global_path', []), ensure_ascii=False, default=lambda o: o.__dict__)
            lp_json = json.dumps(data.get('local_path', []), ensure_ascii=False, default=lambda o: o.__dict__)
            obs_json = json.dumps(data.get('obstacles', []), ensure_ascii=False, default=lambda o: o.__dict__)

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
                gp_json,
                lp_json,
                obs_json
            ]
            self.writers['planning'].writerow(row)
            self._flush_if_needed('planning')
        except Exception as e:
            logger.error(f"Planning record error: {e}")

    def record_radar(self, msg_type: str, data: dict):
        if 'radar' not in self.writers: return
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            # Headers: ts, type, obs_c, obs_id, obs_ts, p_time, p_fps, p_in, p_out, p_vox, p_gnd, p_cls, stat_r, stat_c, stat_e, obs_json
            row = [ts, msg_type] + [""] * 14 

            if msg_type == 'lidar_obstacles':
                # obs_count, frame_id, timestamp
                row[2] = data.get('obstacle_count', 0)
                row[3] = data.get('frame_id', 0)
                row[4] = f"{data.get('timestamp_sec', 0):.4f}"
                # 记录障碍物列表JSON
                row[15] = json.dumps(data.get('obstacles', []), ensure_ascii=False, default=lambda o: o.__dict__)
            
            elif msg_type == 'lidar_performance':
                # perf fields
                row[5] = f"{data.get('processing_time_ms', 0):.2f}"
                row[6] = f"{data.get('frame_rate', 0):.2f}"
                row[7] = data.get('input_points', 0)
                row[8] = data.get('filtered_points', 0)
                # 详细耗时
                row[9] = f"{data.get('voxel_filter_time_ms', 0):.2f}"
                row[10] = f"{data.get('ground_segment_time_ms', 0):.2f}"
                row[11] = f"{data.get('clustering_time_ms', 0):.2f}"

            elif msg_type == 'lidar_status':
                # running, connected, error (Indices 12, 13, 14)
                row[12] = 1 if data.get('is_running') else 0
                row[13] = 1 if data.get('lidar_connected') else 0
                row[14] = data.get('error_code', 0)
            
            self.writers['radar'].writerow(row)
            self._flush_if_needed('radar')
        except Exception as e:
            logger.error(f"Radar record error: {e}")

    def close(self):
        for f in self.files.values():
            try:
                f.close()
            except: pass
