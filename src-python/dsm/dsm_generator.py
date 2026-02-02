"""
DSM数据生成器
离线处理录制数据，生成DSM算法所需的标准格式文件（JSON/CSV矩阵）
"""

import os
import json
import csv
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class DSMGenerator:
    """
    DSM数据生成器
    
    核心功能：
    1. 读取录制的CSV数据文件
    2. 根据映射配置进行数据聚合
    3. 生成DSM节点权重矩阵（对角线）
    4. 生成DSM交互权重矩阵（非对角线）
    5. 输出标准格式：JSON或CSV矩阵
    """
    
    def __init__(self, mapping_config):
        """
        初始化DSM生成器
        
        Args:
            mapping_config: MappingConfig实例，包含物理-逻辑映射关系
        """
        self.mapping_config = mapping_config
    
    def generate_dsm_report(
        self,
        session_id: str,
        base_directory: str = "data",
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        output_format: str = "json"
    ) -> Dict[str, Any]:
        """
        生成DSM分析报告
        
        Args:
            session_id: 录制会话ID
            base_directory: 数据基础目录
            start_time: 开始时间戳（可选，用于时间切片）
            end_time: 结束时间戳（可选，用于时间切片）
            output_format: 输出格式（json或csv_matrix）
            
        Returns:
            包含DSM数据的字典
        """
        logger.info(f"开始生成DSM报告: {session_id}")
        
        # 1. 加载原始数据
        # Updated: loader returns new tuple format
        df_fcs, df_planning, df_radar, df_bus = self._load_raw_data(
            session_id, base_directory
        )
        
        # 简单检查是否有数据
        if df_fcs is None and df_bus is None and df_planning is None and df_radar is None:
            # 尝试兼容旧逻辑？不，直接报错提示需要新格式数据
            # 如果是旧数据结构需要迁移，这里暂且认为都在新体系下工作
            pass 
            # raise ValueError(f"会话 {session_id} 没有可用数据")
        
        # 2. 时间切片过滤
        df_fcs, df_planning, df_radar, df_bus = self._filter_by_time(
            df_fcs, df_planning, df_radar, df_bus, start_time, end_time
        )
        
        # 3. 计算DSM节点权重（对角线）
        dsm_nodes = self._calculate_node_weights(df_fcs, df_planning, df_radar, df_bus)
        
        # 4. 计算DSM交互权重（非对角线）
        dsm_edges = self._calculate_edge_weights(df_bus, df_fcs, df_planning)
        
        # 5. 构建完整矩阵
        dsm_matrix = self._build_dsm_matrix(dsm_nodes, dsm_edges)
        
        # 6. 构建返回结果
        result = {
            "meta": {
                "session_id": session_id,
                "generated_at": datetime.now().isoformat(),
                "time_range": {
                    "start": start_time,
                    "end": end_time,
                    "duration": (end_time - start_time) if start_time and end_time else 0
                },
                "data_statistics": {
                    "fcs_records": len(df_fcs) if df_fcs is not None else 0,
                    "planning_records": len(df_planning) if df_planning is not None else 0,
                    "radar_records": len(df_radar) if df_radar is not None else 0,
                    "bus_records": len(df_bus) if df_bus is not None else 0
                }
            },
            "nodes": dsm_nodes,
            "edges": dsm_edges,
            "matrix": dsm_matrix
        }
        
        # 7. 保存到文件
        output_path = self._save_dsm_report(session_id, result, output_format)
        result["output_path"] = output_path
        
        logger.info(f"DSM报告生成完成: {output_path}")
        return result
    
    def _load_raw_data(
        self,
        session_id: str,
        base_directory: str
    ) -> tuple:
        """
        加载原始CSV数据
        适配新的 recorder 文件结构 (fcs_telemetry, planning, radar, bus_traffic)
        
        Returns:
            (df_fcs, df_planning, df_radar, df_bus) 元组
        """
        session_dir = os.path.join(base_directory, session_id)
        
        df_fcs = None
        df_planning = None
        df_radar = None
        df_bus = None
        
        # 1. 加载FCS遥测数据 (包含 STATES, DATACTRL, GNCBUS, PWMS 等)
        fcs_path = os.path.join(session_dir, "fcs_telemetry.csv")
        if os.path.exists(fcs_path):
            try:
                # 尝试读取，注意 fcs_telemetry 可能行数很多
                # 使用 low_memory=False 防止列类型推断警告，因为有很多空列
                df_fcs = pd.read_csv(fcs_path, low_memory=False)
                
                # [关键修正] 数据稀疏性处理：
                # 也是UDP多包复用一张宽表导致的，必须使用前向填充(ffill)将上一时刻的状态延续
                # 否则大量空白或0值会导致 std() 计算错误
                df_fcs.sort_values('timestamp', inplace=True)
                df_fcs.fillna(method='ffill', inplace=True)
                df_fcs.fillna(0, inplace=True) # 剩下的开头空值填0
                
                logger.info(f"加载FCS遥测数据: {len(df_fcs)} 条记录 (已执行ffill)")
            except Exception as e:
                logger.error(f"加载FCS遥测数据失败: {e}")
        
        # 2. 加载规划遥测数据
        planning_path = os.path.join(session_dir, "planning_telemetry.csv")
        if os.path.exists(planning_path):
            try:
                df_planning = pd.read_csv(planning_path)
                logger.info(f"加载规划遥测数据: {len(df_planning)} 条记录")
            except Exception as e:
                logger.error(f"加载规划遥测数据失败: {e}")
        
        # 3. 加载雷达/障碍物数据
        radar_path = os.path.join(session_dir, "radar_data.csv")
        if os.path.exists(radar_path):
            try:
                df_radar = pd.read_csv(radar_path)
                logger.info(f"加载雷达数据: {len(df_radar)} 条记录")
            except Exception as e:
                logger.error(f"加载雷达数据失败: {e}")
        
        # 4. 加载总线通信数据 (用于计算频率、延迟)
        bus_path = os.path.join(session_dir, "bus_traffic.csv")
        if os.path.exists(bus_path):
            try:
                df_bus = pd.read_csv(bus_path)
                logger.info(f"加载总线通信数据: {len(df_bus)} 条记录")
            except Exception as e:
                logger.error(f"加载总线通信数据失败: {e}")
        
        # 为了兼容旧代码变量命名，这里返回新的数据集
        # 注意：下面的方法签名和调用处也需要修改
        return df_fcs, df_planning, df_radar, df_bus 

    def _filter_by_time(
        self,
        df_fcs: pd.DataFrame,
        df_planning: pd.DataFrame,
        df_radar: pd.DataFrame,
        df_bus: pd.DataFrame,
        start_time: Optional[float],
        end_time: Optional[float]
    ) -> tuple:
        """按时间范围过滤数据"""
        if start_time is None and end_time is None:
            return df_fcs, df_planning, df_radar, df_bus
        
        data_frames = [df_fcs, df_planning, df_radar, df_bus]
        filtered_dfs = []
        
        for df in data_frames:
            if df is not None and 'timestamp' in df.columns:
                mask = (df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)
                filtered_dfs.append(df[mask])
            else:
                filtered_dfs.append(df)
        
        logger.info(f"时间切片过滤完成: [{start_time}, {end_time}]")
        return tuple(filtered_dfs)
    
    def _calculate_node_weights(
        self,
        df_fcs: pd.DataFrame, # 取代了 resources, flight, futaba, gncbus
        df_planning: pd.DataFrame,
        df_radar: pd.DataFrame,
        df_bus: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """
        计算DSM节点权重 (Updated for MDC610)
        """
        nodes = []
        nodes_config = self.mapping_config.get_nodes()
        
        for i, node_cfg in enumerate(nodes_config):
            lf_name = node_cfg['logical_function']
            phys_source = node_cfg['physical_source']
            
            data_type = phys_source.get('type', 'cpu_load')
            node_id = phys_source.get('filter_id', 0)
            metric_type = phys_source.get('metric', 'avg_load')
            
            weight = 0.0
            data_source_name = "unknown"
            
            # --- 1. 处理控制输入 (LF_RC_Parser) ---
            if data_type == 'control_input':
                # 源自 fcs_telemetry
                # [关键修正] 更新字段名为实际存在的 Tele_ftb 系列或 GNCBus 指令
                if df_fcs is not None and not df_fcs.empty:
                    try:
                        # 优先使用遥控器输入 (Futaba)
                        if 'Tele_ftb_Col' in df_fcs.columns:
                             weight = df_fcs['Tele_ftb_Col'].std() 
                        elif 'GNCBus_TokenMode_col_state' in df_fcs.columns:
                             weight = df_fcs['GNCBus_TokenMode_col_state'].std()
                        else:
                             weight = 0.5 
                        data_source_name = "fcs_telemetry (futaba/gncbus)"
                    except Exception:
                        weight = 0.5

            # --- 初始化特征画像 ---
            profile = {
                "avg_execution_time_ms": 0.0,
                "cpu_load_factor": 0.0,
                "cpu_load_p95": 0.0, # [Updated] P95 Load
                "data_rate_bps": 0.0,
                "jitter_ms": 0.0,
                "jitter_p95_ms": 0.0, # [Updated] P95 Jitter
                "nav_rmse": 0.0,   # [MOP] 导航误差
                "avg_power_w": 0.0, # [TPM] 平均功耗
                "reliability_score": 1.0 # [MOE] 可靠性 (1.0=Perfect)
            }

            # --- 2. 处理 GNC 状态/指令 (LF_INS_Parser, LF_Flight_Control) ---
            if data_type in ['gnc_state', 'gnc_command']:
                # 源自 fcs_telemetry (STATES, GNCBUS段)
                if df_fcs is not None and not df_fcs.empty:
                    if data_type == 'gnc_state':
                         # 惯导解析负载与频率正相关
                         weight = 0.8
                         profile["avg_execution_time_ms"] = 2.5
                         profile["cpu_load_factor"] = 0.15
                         profile["cpu_load_p95"] = 0.20 # Mock P95
                         # 计算导航误差 (RMSE)
                         profile["nav_rmse"] = self._calc_nav_rmse(df_fcs)
                         
                    elif data_type == 'gnc_command':
                         # 飞控计算负载与指令复杂性相关
                         if 'gncbus_cmd_phi' in df_fcs.columns:
                             weight = df_fcs['gncbus_cmd_phi'].std() + 1.0
                         else:
                             weight = 1.0
                         profile["avg_execution_time_ms"] = 1.5
                         profile["cpu_load_factor"] = 0.12
                         profile["cpu_load_p95"] = 0.18 # Mock P95

                    jitter, jitter_p95 = self._calc_jitter(df_fcs)
                    profile["jitter_ms"] = jitter
                    profile["jitter_p95_ms"] = jitter_p95
                    data_source_name = "fcs_telemetry (states/gncbus)"

            # --- 3. 处理感知/雷达 (LF_Perception) ---
            elif 'cpu_load' in data_type:
                # 0x51 OBSTACLE_INFO 数量越多，负载原本越高
                # radar_data.csv 列名: timestamp, obstacle_count, proc_time_ms...
                if df_radar is not None and not df_radar.empty:
                    weight = df_radar['obstacle_count'].mean() if 'obstacle_count' in df_radar.columns else 0.5
                    data_source_name = "radar_data.csv"
                    
                    if 'proc_time_ms' in df_radar.columns:
                        avg_proc = df_radar['proc_time_ms'].mean()
                        profile["avg_execution_time_ms"] = avg_proc
                        # 假设 10Hz
                        profile["cpu_load_factor"] = avg_proc / 100.0

            # --- 4. 处理规划 (LF_Path_Planning) ---
            elif data_type == 'planning_telemetry':
                if df_planning is not None and not df_planning.empty:
                    weight = 0.8 # 简化
                    data_source_name = "planning_telemetry.csv"
                    profile["avg_execution_time_ms"] = 5.0
                    profile["cpu_load_factor"] = 0.2

            # --- 5. 通信流量 (LF_Communication) ---
            elif data_type == 'traffic_volume' and df_bus is not None:
                 if not df_bus.empty:
                     # 统计特定 msg_id 的总字节数
                     subset = df_bus[df_bus['msg_id'] == node_id]
                     total_bytes = subset['msg_size'].sum() if not subset.empty else 0
                     weight = total_bytes / 1024.0 # KB
                     data_source_name = "bus_traffic.csv"
                     
                     profile["data_rate_bps"] = total_bytes
                     profile["cpu_load_factor"] = 0.05
            
            # --- 6. 驱动输出 (LF_Motor_Driver) ---
            elif data_type == 'actuator_output':
                 if df_fcs is not None and 'pwm1' in df_fcs.columns:
                     weight = df_fcs[['pwm1','pwm2','pwm3','pwm4']].std().mean()
                     data_source_name = "fcs_telemetry (pwms)"
                     profile["cpu_load_factor"] = 0.02
                     # 计算平均功耗 (W)
                     profile["avg_power_w"] = self._calc_power(df_fcs)

            attributes = {
                'description': phys_source.get('description', ''),
                'data_type': data_type,
                'filter_id': node_id,
                'data_source': data_source_name,
                'profile': profile
            }
            
            nodes.append({
                "index": i,
                "name": lf_name,
                "own_cost": round(weight, 4),
                "attributes": attributes
            })
        
        logger.info(f"计算节点权重完成: {len(nodes)} 个节点")
        return nodes

    def _calc_jitter(self, df):
        """
        计算时间戳抖动 (ms)
        Returns: (mean_jitter, p95_jitter)
        """
        try:
            if df is None or 'timestamp' not in df.columns or len(df) < 2:
                return 0.0, 0.0
            
            diffs = df['timestamp'].diff().dropna() * 1000 # to ms
            # Jitter is deviation from expected period. 
            # Simplified: Standard deviation of diffs
            
            mean_jitter = diffs.std()
            p95_jitter = np.percentile(diffs, 95) - diffs.mean() # Deviation at 95th percentile
            
            return float(mean_jitter), float(p95_jitter)
        except:
            return 0.0, 0.0
            
    def _calc_nav_rmse(self, df: pd.DataFrame) -> float:
        """
        [MOP] 计算导航跟踪误差 (RMSE)
        逻辑: 比较 CmdValue (指令) 与 ActualValue (实际) 的欧氏距离
        (假设列名: GNCBus_CmdValue_height_cmd vs states_height)
        """
        try:
            if df is None: return 0.0
            
            # 定义成对的列名 (指令 vs 实际)
            # 注意：实际项目中需根据 csv_helper_full.py 确认列名
            pairs = [
                ('GNCBus_CmdValue_height_cmd', 'states_height'),
                ('GNCBus_CmdValue_Vy_cmd', 'states_Vy_GS'),
                ('GNCBus_CmdValue_Vx_cmd', 'states_Vx_GS')
            ]
            
            sq_errors = []
            for cmd_col, act_col in pairs:
                if cmd_col in df.columns and act_col in df.columns:
                    # 计算 (Cmd - Act)^2
                    diff = df[cmd_col] - df[act_col]
                    sq_errors.append(diff ** 2)
            
            if not sq_errors:
                return 0.0
                
            # 合并所有维度的误差
            total_sq_error = pd.concat(sq_errors, axis=1).sum(axis=1)
            rmse = np.sqrt(total_sq_error.mean())
            return float(rmse)
        except Exception as e:
            logger.warning(f"Error calculating RMSE: {e}")
            return 0.0

    def _calc_power(self, df: pd.DataFrame) -> float:
        """
        [TPM] 计算平均功耗 (W)
        逻辑: 提取 ESC 电流/电压数据进行估算
        """
        try:
            if df is None: return 0.0
            
            # fcs_telemetry 包含 esc1_power_rating_pct (百分比)
            # 假设最大功率 500W per motor
            MAX_POWER_PER_MOTOR = 500.0
            
            esc_cols = [f'esc{i}_power_rating_pct' for i in range(1, 7)]
            valid_cols = [c for c in esc_cols if c in df.columns]
            
            if not valid_cols:
                return 0.0
                
            # 计算所有电机平均百分比
            avg_pct = df[valid_cols].mean().mean()
            # 估算总功率: 6 motors * 500W * pct
            total_power = 6 * MAX_POWER_PER_MOTOR * (avg_pct / 100.0)
            return float(total_power)
        except Exception:
            return 0.0
    
    def _calculate_edge_weights(
        self,
        df_bus: pd.DataFrame,
        df_fcs: pd.DataFrame, # 取代了 df_gncbus, df_futaba
        df_planning: pd.DataFrame # 备用，规划数据
    ) -> List[Dict[str, Any]]:
        """
        计算DSM交互权重（非对角线值）
        适配新的 recorder 文件结构 (使用 df_fcs)
        """
        edges = []
        edges_config = self.mapping_config.get_edges()
        
        for edge_cfg in edges_config:
            fe_name = edge_cfg['functional_exchange']
            source_lf = edge_cfg['source_lf']
            target_lf = edge_cfg['target_lf']
            phys_source = edge_cfg['physical_source']
            
            data_type = phys_source.get('type', 'bus_traffic')
            msg_id = phys_source.get('filter_id', 0)
            weight_formula = phys_source.get('weight_formula', 'count')
            
            interaction_weight = 0
            data_source_info = ""
            profile = { "avg_packet_size": 0.0, "frequency_hz": 0.0 }
            
            # --- 1. 总线通信流量 (适用于 SoC Adapter 等) ---
            if data_type == 'bus_traffic':
                if df_bus is not None and not df_bus.empty:
                    msg_data = df_bus[df_bus['msg_id'] == msg_id]
                    
                    if not msg_data.empty:
                        count = len(msg_data)
                        duration = msg_data['timestamp'].max() - msg_data['timestamp'].min()
                        frequency = count / duration if duration > 0 else 0
                        avg_size = msg_data['msg_size'].mean()
                        avg_latency = 0.0 
                        
                        profile["avg_packet_size"] = avg_size
                        profile["frequency_hz"] = frequency

                        formula = weight_formula.replace('count', str(count))
                        formula = formula.replace('frequency', str(frequency))
                        formula = formula.replace('size', str(avg_size))
                        formula = formula.replace('latency', str(avg_latency))
                        
                        try:
                            interaction_weight = float(eval(formula))
                        except Exception as e:
                            interaction_weight = count
                        
                        data_source_info = f"bus_traffic.csv (msg_id=0x{msg_id:02X})"
            
            # --- 2. GNC 指令变化 (LF_Trajectory_Cmd) ---
            elif data_type == 'gnc_command_change':
                if df_fcs is not None and not df_fcs.empty:
                    # 使用 GNCBus_CmdValue_phi_cmd 等字段
                    cmd_col = self._get_cmd_column_by_msg_id(msg_id)
                    if cmd_col and cmd_col in df_fcs.columns:
                        std_val = df_fcs[cmd_col].std()
                        # 权重公式: std * factor
                        try:
                            # 简单的eval支持 'std' 变量
                            formula = weight_formula.replace('std', str(std_val))
                            interaction_weight = float(eval(formula))
                        except:
                            interaction_weight = std_val
                        
                        profile["frequency_hz"] = 50.0 # GNC typical
                        data_source_info = f"fcs_telemetry ({cmd_col})"
            
            # --- 3. 遥控输入活动 (FE_RC_Data) ---
            elif data_type == 'remote_input_activity':
                if df_fcs is not None and not df_fcs.empty:
                     col_name = "Tele_ftb_Switch" 
                     if msg_id == 0x46 or msg_id == 0x43:
                         col_name = "Tele_ftb_Switch" 
                         diffs = df_fcs[col_name].diff().abs().mean() if col_name in df_fcs.columns else 0
                         interaction_weight = diffs * len(df_fcs)
                         profile["avg_packet_size"] = 16.0
                         data_source_info = f"fcs_telemetry ({col_name})"
            
            if interaction_weight > 0.001:
                edges.append({
                    "from": source_lf,
                    "to": target_lf,
                    "weight": round(interaction_weight, 4),
                    "type": "DataFlow",
                    "functional_exchange": fe_name,
                    "attributes": {
                        'description': phys_source.get('description', ''),
                        'data_source': data_source_info,
                        'profile': profile
                    }
                })
        
        logger.info(f"计算交互权重完成: {len(edges)} 条边")
        return edges
    
    def _get_cmd_column_by_msg_id(self, msg_id: int) -> Optional[str]:
        """GNCBus 列名映射 - Updated"""
        # 0x44 对应 GNCBus
        # 这里 msg_id 可能是 0x44 (config中配置的)
        if msg_id == 0x44:
            return 'GNCBus_CmdValue_phi_cmd' # 示例，用横滚角指令代表活动度
        return None

    def _get_remote_column_by_msg_id(self, msg_id: int) -> Optional[str]:
        """Remote 列名映射 - Updated"""
        # DATAFUTABA (0x46) or DATACTRL (0x43)
        if msg_id == 0x46 or msg_id == 0x43:
            return 'Tele_ftb_Roll'
        return None
    
    def _build_dsm_matrix(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> List[List[float]]:
        """
        构建DSM矩阵
        
        矩阵格式：
        - 对角线：节点自身代价
        - 非对角线：交互强度
        """
        n = len(nodes)
        matrix = np.zeros((n, n))
        
        # 构建节点名称到索引的映射
        node_name_to_index = {
            node['name']: node['index']
            for node in nodes
        }
        
        # 填充对角线（节点自身代价）
        for node in nodes:
            idx = node['index']
            matrix[idx, idx] = node['own_cost']
        
        # 填充非对角线（交互强度）
        for edge in edges:
            source_name = edge['from']
            target_name = edge['to']
            weight = edge['weight']
            
            if source_name in node_name_to_index and target_name in node_name_to_index:
                i = node_name_to_index[source_name]
                j = node_name_to_index[target_name]
                matrix[i, j] = weight
        
        return matrix.tolist()
    
    def _infer_safety_level(self, lf_name: str) -> str:
        """
        根据逻辑功能名称推断安全等级
        """
        if 'Motor' in lf_name or 'Control' in lf_name:
            return 'DAL-A'  # 最高安全等级
        elif 'Navigation' in lf_name or 'Sensor' in lf_name:
            return 'DAL-B'
        else:
            return 'DAL-C'
    
    def _save_dsm_report(
        self,
        session_id: str,
        report: Dict[str, Any],
        output_format: str
    ) -> str:
        """
        保存DSM报告到文件
        """
        output_dir = os.path.join("data", session_id)
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if output_format == "json":
            # JSON格式
            output_path = os.path.join(output_dir, f"dsm_report_{timestamp}.json")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        
        elif output_format == "csv_matrix":
            # CSV矩阵格式
            output_path = os.path.join(output_dir, f"dsm_matrix_{timestamp}.csv")
            
            nodes = report['nodes']
            matrix = report['matrix']
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # 写入表头
                header = ['']
                for node in nodes:
                    header.append(node['name'])
                writer.writerow(header)
                
                # 写入矩阵数据
                for i, row in enumerate(matrix):
                    row_data = [nodes[i]['name']]
                    row_data.extend([f"{val:.4f}" for val in row])
                    writer.writerow(row_data)
        
        else:
            raise ValueError(f"不支持的输出格式: {output_format}")
        
        logger.info(f"DSM报告已保存: {output_path}")
        return output_path
    
    def export_for_matlab(
        self,
        report: Dict[str, Any],
        output_path: str
    ):
        """
        导出MATLAB可用的.mat文件
        
        Args:
            report: DSM报告字典
            output_path: 输出文件路径
        """
        try:
            from scipy.io import savemat
            
            # 构建MATLAB数据结构
            matlab_data = {
                'DSM_Matrix': np.array(report['matrix']),
                'Node_Names': [node['name'] for node in report['nodes']],
                'Metadata': {
                    'session_id': report['meta']['session_id'],
                    'generated_at': report['meta']['generated_at']
                }
            }
            
            # 保存.mat文件
            savemat(output_path, matlab_data)
            logger.info(f"MATLAB格式文件已导出: {output_path}")
        except ImportError:
            logger.error("未安装scipy库，无法导出MATLAB格式")
            raise
        except Exception as e:
            logger.error(f"导出MATLAB格式失败: {e}")
            raise