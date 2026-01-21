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
        df_flight, df_resources, df_bus, df_futaba, df_gncbus = self._load_raw_data(
            session_id, base_directory
        )
        
        if df_flight is None and df_resources is None and df_bus is None and df_futaba is None and df_gncbus is None:
            raise ValueError(f"会话 {session_id} 没有可用数据")
        
        # 2. 时间切片过滤（如果指定了时间范围）
        df_flight, df_resources, df_bus, df_futaba, df_gncbus = self._filter_by_time(
            df_flight, df_resources, df_bus, df_futaba, df_gncbus, start_time, end_time
        )
        
        # 3. 计算DSM节点权重（对角线）
        dsm_nodes = self._calculate_node_weights(df_resources, df_flight, df_futaba, df_gncbus)
        
        # 4. 计算DSM交互权重（非对角线）
        dsm_edges = self._calculate_edge_weights(df_bus, df_gncbus, df_futaba)
        
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
                    "flight_records": len(df_flight) if df_flight is not None else 0,
                    "resource_records": len(df_resources) if df_resources is not None else 0,
                    "bus_records": len(df_bus) if df_bus is not None else 0,
                    "futaba_records": len(df_futaba) if df_futaba is not None else 0,
                    "gncbus_records": len(df_gncbus) if df_gncbus is not None else 0
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
        
        Returns:
            (df_flight, df_resources, df_bus, df_futaba, df_gncbus) 元组
        """
        session_dir = os.path.join(base_directory, session_id)
        
        df_flight = None
        df_resources = None
        df_bus = None
        df_futaba = None
        df_gncbus = None
        
        # 加载飞行性能数据
        flight_path = os.path.join(session_dir, "flight_perf.csv")
        if os.path.exists(flight_path):
            try:
                df_flight = pd.read_csv(flight_path)
                logger.info(f"加载飞行性能数据: {len(df_flight)} 条记录")
            except Exception as e:
                logger.error(f"加载飞行性能数据失败: {e}")
        
        # 加载资源数据
        resources_path = os.path.join(session_dir, "resources.csv")
        if os.path.exists(resources_path):
            try:
                df_resources = pd.read_csv(resources_path)
                logger.info(f"加载资源数据: {len(df_resources)} 条记录")
            except Exception as e:
                logger.error(f"加载资源数据失败: {e}")
        
        # 加载总线通信数据
        bus_path = os.path.join(session_dir, "bus_traffic.csv")
        if os.path.exists(bus_path):
            try:
                df_bus = pd.read_csv(bus_path)
                logger.info(f"加载总线通信数据: {len(df_bus)} 条记录")
            except Exception as e:
                logger.error(f"加载总线通信数据失败: {e}")
        
        # 加载Futaba遥控数据
        futaba_path = os.path.join(session_dir, "futaba_remote.csv")
        if os.path.exists(futaba_path):
            try:
                df_futaba = pd.read_csv(futaba_path)
                logger.info(f"加载Futaba遥控数据: {len(df_futaba)} 条记录")
            except Exception as e:
                logger.error(f"加载Futaba遥控数据失败: {e}")
        
        # 加载GN&C总线数据
        gncbus_path = os.path.join(session_dir, "gncbus.csv")
        if os.path.exists(gncbus_path):
            try:
                df_gncbus = pd.read_csv(gncbus_path)
                logger.info(f"加载GN&C总线数据: {len(df_gncbus)} 条记录")
            except Exception as e:
                logger.error(f"加载GN&C总线数据失败: {e}")
        
        return df_flight, df_resources, df_bus, df_futaba, df_gncbus
    
    def _filter_by_time(
        self,
        df_flight: pd.DataFrame,
        df_resources: pd.DataFrame,
        df_bus: pd.DataFrame,
        df_futaba: pd.DataFrame,
        df_gncbus: pd.DataFrame,
        start_time: Optional[float],
        end_time: Optional[float]
    ) -> tuple:
        """
        按时间范围过滤数据
        """
        if start_time is None and end_time is None:
            return df_flight, df_resources, df_bus, df_futaba, df_gncbus
        
        if df_flight is not None:
            mask = (df_flight['timestamp'] >= start_time) & (df_flight['timestamp'] <= end_time)
            df_flight = df_flight[mask]
        
        if df_resources is not None:
            mask = (df_resources['timestamp'] >= start_time) & (df_resources['timestamp'] <= end_time)
            df_resources = df_resources[mask]
        
        if df_bus is not None:
            mask = (df_bus['timestamp'] >= start_time) & (df_bus['timestamp'] <= end_time)
            df_bus = df_bus[mask]
        
        if df_futaba is not None:
            mask = (df_futaba['timestamp'] >= start_time) & (df_futaba['timestamp'] <= end_time)
            df_futaba = df_futaba[mask]
        
        if df_gncbus is not None:
            mask = (df_gncbus['timestamp'] >= start_time) & (df_gncbus['timestamp'] <= end_time)
            df_gncbus = df_gncbus[mask]
        
        logger.info(f"时间切片过滤完成: [{start_time}, {end_time}]")
        return df_flight, df_resources, df_bus, df_futaba, df_gncbus
    
    def _calculate_node_weights(
        self,
        df_resources: pd.DataFrame,
        df_flight: pd.DataFrame,
        df_futaba: pd.DataFrame,
        df_gncbus: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """
        计算DSM节点权重（对角线值）
        
        节点权重反映每个逻辑功能的自身代价（如CPU负载、计算复杂度）
        现在支持多种数据源：资源数据、飞行数据、Futaba数据、GN&C总线数据
        """
        nodes = []
        nodes_config = self.mapping_config.get_nodes()
        
        for i, node_cfg in enumerate(nodes_config):
            lf_name = node_cfg['logical_function']
            phys_source = node_cfg['physical_source']
            
            # 获取物理数据源类型
            data_type = phys_source.get('type', 'cpu_load')
            node_id = phys_source.get('filter_id', 0)
            metric_type = phys_source.get('metric', 'avg_load')
            
            # 根据数据类型计算权重
            weight = 0.0
            
            if data_type == 'cpu_load':
                # 使用资源数据（CPU负载）
                if df_resources is not None and not df_resources.empty:
                    # 根据node_id筛选数据（这里用msg_id映射到task_id）
                    node_data = df_resources[df_resources['task_id'] == node_id]
                    
                    if not node_data.empty:
                        if metric_type == 'avg_load':
                            weight = node_data['cpu_load'].mean()
                        elif metric_type == 'peak_load':
                            weight = node_data['cpu_load'].max()
                        else:
                            weight = node_data['cpu_load'].mean()
            
            elif data_type == 'control_input':
                # 使用Futaba遥控数据（控制输入）
                if df_futaba is not None and not df_futaba.empty:
                    if metric_type == 'avg_roll':
                        weight = abs(df_futaba['remote_roll'].mean() - 1000) / 1000.0  # 归一化到0-1
                    elif metric_type == 'avg_pitch':
                        weight = abs(df_futaba['remote_pitch'].mean() - 1000) / 1000.0
                    elif metric_type == 'avg_yaw':
                        weight = abs(df_futaba['remote_yaw'].mean() - 1000) / 1000.0
                    elif metric_type == 'avg_throttle':
                        weight = df_futaba['remote_throttle'].mean() / 2000.0
                    else:
                        weight = 0.5  # 默认值
            
            elif data_type == 'gnc_command':
                # 使用GN&C总线数据（GNC指令值）
                if df_gncbus is not None and not df_gncbus.empty:
                    if metric_type == 'cmd_phi_std':
                        weight = df_gncbus['cmd_phi'].std() if len(df_gncbus) > 1 else 0.0
                    elif metric_type == 'cmd_vx_avg':
                        weight = abs(df_gncbus['cmd_vx'].mean()) / 10.0  # 假设最大速度10m/s
                    elif metric_type == 'cmd_height_avg':
                        weight = df_gncbus['cmd_height'].mean() / 100.0  # 假设最大高度100m
                    else:
                        weight = 0.3  # 默认值
            
            # 额外的元数据
            attributes = {
                'description': node_cfg.get('physical_source', {}).get('description', ''),
                'data_type': data_type,
                'filter_id': node_id,
                'metric_type': metric_type,
                'safety_level': self._infer_safety_level(lf_name)
            }
            
            # 记录实际使用的数据源
            if data_type == 'cpu_load' and df_resources is not None:
                attributes['data_source'] = f"resources.csv (filter_id={node_id})"
            elif data_type == 'control_input' and df_futaba is not None:
                attributes['data_source'] = f"futaba_remote.csv ({len(df_futaba)} records)"
            elif data_type == 'gnc_command' and df_gncbus is not None:
                attributes['data_source'] = f"gncbus.csv ({len(df_gncbus)} records)"
            
            nodes.append({
                "index": i,
                "name": lf_name,
                "own_cost": round(weight, 4),
                "attributes": attributes
            })
        
        logger.info(f"计算节点权重完成: {len(nodes)} 个节点")
        return nodes
    
    def _calculate_edge_weights(
        self,
        df_bus: pd.DataFrame,
        df_gncbus: pd.DataFrame,
        df_futaba: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """
        计算DSM交互权重（非对角线值）
        
        交互权重反映模块间的通信强度（如数据量、频率、延迟）
        现在支持多种数据源：总线通信、GN&C指令、Futaba遥控输入
        """
        edges = []
        edges_config = self.mapping_config.get_edges()
        
        for edge_cfg in edges_config:
            fe_name = edge_cfg['functional_exchange']
            source_lf = edge_cfg['source_lf']
            target_lf = edge_cfg['target_lf']
            phys_source = edge_cfg['physical_source']
            
            # 获取物理数据源类型
            data_type = phys_source.get('type', 'bus_traffic')
            msg_id = phys_source.get('filter_id', 0)
            weight_formula = phys_source.get('weight_formula', 'count')
            
            # 根据数据类型计算权重
            interaction_weight = 0
            data_source_info = ""
            
            if data_type == 'bus_traffic':
                # 使用总线通信数据
                if df_bus is not None and not df_bus.empty:
                    msg_data = df_bus[df_bus['msg_id'] == msg_id]
                    
                    if not msg_data.empty:
                        # 计算公式变量
                        count = len(msg_data)
                        duration = msg_data['timestamp'].max() - msg_data['timestamp'].min()
                        frequency = count / duration if duration > 0 else 0
                        avg_size = msg_data['msg_size'].mean()
                        avg_latency = msg_data.get('latency_ms', pd.Series([0])).mean()
                        
                        # 根据公式计算权重
                        formula = weight_formula.replace('count', str(count))
                        formula = formula.replace('frequency', str(frequency))
                        formula = formula.replace('size', str(avg_size))
                        formula = formula.replace('latency', str(avg_latency))
                        
                        try:
                            interaction_weight = float(eval(formula))
                        except Exception as e:
                            logger.warning(f"公式计算失败: {formula}, 使用默认值")
                            interaction_weight = count
                        
                        data_source_info = f"bus_traffic.csv (msg_id=0x{msg_id:02X}, {count} msgs)"
            
            elif data_type == 'gnc_command_change':
                # 使用GN&C总线数据（计算指令变化率）
                if df_gncbus is not None and not df_gncbus.empty:
                    # 计算指令的变化率（作为交互强度的代理）
                    cmd_column = self._get_cmd_column_by_msg_id(msg_id)
                    
                    if cmd_column and cmd_column in df_gncbus.columns:
                        cmd_values = df_gncbus[cmd_column].values
                        # 计算标准差（变化越频繁，交互越强）
                        std_val = np.std(cmd_values) if len(cmd_values) > 1 else 0.0
                        interaction_weight = std_val
                        
                        data_source_info = f"gncbus.csv (cmd={cmd_column}, std={std_val:.4f})"
            
            elif data_type == 'remote_input_activity':
                # 使用Futaba遥控数据（计算遥控输入活动度）
                if df_futaba is not None and not df_futaba.empty:
                    # 计算遥控输入的变化率
                    input_column = self._get_remote_column_by_msg_id(msg_id)
                    
                    if input_column and input_column in df_futaba.columns:
                        input_values = df_futaba[input_column].values
                        # 计算一阶差分（相邻值的差）
                        diff_values = np.abs(np.diff(input_values))
                        activity_score = np.mean(diff_values)
                        
                        # 替换公式中的变量
                        formula = weight_formula.replace('activity', str(activity_score))
                        formula = formula.replace('count', str(len(df_futaba)))
                        
                        try:
                            interaction_weight = float(eval(formula))
                        except Exception as e:
                            logger.warning(f"公式计算失败: {formula}, 使用默认值")
                            interaction_weight = activity_score
                        
                        data_source_info = f"futaba_remote.csv (input={input_column}, activity={activity_score:.4f})"
            
            # 只添加有权重的边
            if interaction_weight > 0.001:  # 避免权重过小的边
                edges.append({
                    "from": source_lf,
                    "to": target_lf,
                    "weight": round(interaction_weight, 4),
                    "type": "DataFlow",
                    "functional_exchange": fe_name,
                    "attributes": {
                        'description': phys_source.get('description', ''),
                        'data_type': data_type,
                        'msg_id': msg_id,
                        'formula': weight_formula,
                        'data_source': data_source_info
                    }
                })
        
        logger.info(f"计算交互权重完成: {len(edges)} 条边")
        return edges
    
    def _get_cmd_column_by_msg_id(self, msg_id: int) -> Optional[str]:
        """
        根据消息ID获取对应的GN&C命令列名
        
        Args:
            msg_id: 消息ID
        
        Returns:
            命令列名，如果未找到则返回None
        """
        # 映射关系：消息ID -> GNC命令列
        cmd_mapping = {
            0x44: 'cmd_phi',  # fcs_gncbus消息
            0x45: 'cmd_hdot',
            0x46: 'cmd_r',
            0x47: 'cmd_psi',
            0x48: 'cmd_vx',
            0x49: 'cmd_vy',
            0x4A: 'cmd_height'
        }
        return cmd_mapping.get(msg_id)
    
    def _get_remote_column_by_msg_id(self, msg_id: int) -> Optional[str]:
        """
        根据消息ID获取对应的遥控输入列名
        
        Args:
            msg_id: 消息ID
        
        Returns:
            遥控输入列名，如果未找到则返回None
        """
        # 映射关系：消息ID -> 遥控输入列
        remote_mapping = {
            0x41: 'remote_roll',  # 假设映射
            0x42: 'remote_pitch',
            0x43: 'remote_yaw',
            0x46: 'remote_throttle'  # Futaba遥控消息
        }
        return remote_mapping.get(msg_id)
    
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