"""
地面站配置管理
"""

import os
from typing import Dict, Any
from dataclasses import dataclass, field

@dataclass
class UDPConfig:
    """UDP通信配置"""
    # 接收配置（地面站监听）
    listen_host: str = "0.0.0.0"
    listen_port: int = 30509
    listen_ports: list = field(default_factory=lambda: [30509, 18507, 18511])
    
    # 发送配置（地面站发送指令到飞控）
    target_ip: str = "127.0.0.1"
    target_port: int = 18504

class Config:
    """全局配置单例"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not Config._initialized:
            self.udp_config = UDPConfig()
            self._load_from_env()
            Config._initialized = True
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # 默认监听端口（地面站使用的监听端口）
        # - 30509: 接收飞控遥测数据
        # - 18507: 接收LiDAR数据
        # - 18511: 接收规划遥测数据
        self.udp_config.listen_ports = [30509, 18507, 18511]
        self.udp_config.listen_port = 30509
        
        # 默认发送目标（飞控IP和端口）
        # 127.0.0.1:18504（默认本地测试）
        self.udp_config.target_ip = "127.0.0.1"
        self.udp_config.target_port = 18504
        
        # 环境变量覆盖（优先级高于默认值）
        listen_port = os.getenv("GCS_LISTEN_PORT")
        if listen_port:
            self.udp_config.listen_port = int(listen_port)
        
        target_ip = os.getenv("GCS_TARGET_IP")
        if target_ip:
            self.udp_config.target_ip = target_ip
        
        target_port = os.getenv("GCS_TARGET_PORT")
        if target_port:
            self.udp_config.target_port = int(target_port)
    
    def get_udp_config(self) -> UDPConfig:
        """获取UDP配置"""
        return self.udp_config
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于API返回）"""
        return {
            "listen": {
                "host": self.udp_config.listen_host,
                "port": self.udp_config.listen_port
            },
            "target": {
                "ip": self.udp_config.target_ip,
                "port": self.udp_config.target_port
            }
        }
    
    def update_from_dict(self, data: Dict[str, Any]):
        """从字典更新配置"""
        if "listen" in data:
            if "host" in data["listen"]:
                self.udp_config.listen_host = data["listen"]["host"]
            if "port" in data["listen"]:
                self.udp_config.listen_port = data["listen"]["port"]
            if "ports" in data["listen"]:
                self.udp_config.listen_ports = data["listen"]["ports"]
        
        if "target" in data:
            if "ip" in data["target"]:
                self.udp_config.target_ip = data["target"]["ip"]
            if "port" in data["target"]:
                self.udp_config.target_port = data["target"]["port"]
    
    def print_config(self):
        """打印当前配置"""
        print("=" * 60)
        print("地面站配置信息")
        print("=" * 60)
        print(f"接收配置: {self.udp_config.listen_host}:{self.udp_config.listen_port}")
        print(f"发送目标: {self.udp_config.target_ip}:{self.udp_config.target_port}")
        print("=" * 60)

# ================================================================
# DSM映射配置类
# ================================================================

class MappingConfig:
    """
    DSM物理-逻辑映射配置
    
    负责定义物理数据与逻辑架构的对应关系：
    - 节点映射：物理任务 -> 逻辑功能（用于计算DSM对角线权重）
    - 交互映射：物理消息 -> 功能交换（用于计算DSM非对角线权重）
    """
    
    def __init__(self):
        """初始化映射配置"""
        self.nodes = self._init_nodes()
        self.edges = self._init_edges()
    
    def _init_nodes(self) -> list:
        """
        初始化节点配置（逻辑功能定义）
        
        返回：
            节点配置列表，每个节点包含：
            - logical_function: 逻辑功能名称
            - physical_source: 物理数据源配置
              - type: 数据类型 (cpu_load, control_input, gnc_command)
              - filter_id: 过滤ID（消息ID或任务ID）
              - metric: 指标类型 (avg_load, peak_load, avg_roll等)
              - description: 描述信息
        """
        return [
            {
                "logical_function": "LF_Navigation",
                "physical_source": {
                    "type": "cpu_load",
                    "filter_id": 0x42,  # fcs_states消息ID
                    "metric": "avg_load",
                    "description": "导航功能CPU负载"
                }
            },
            {
                "logical_function": "LF_Motor_Control",
                "physical_source": {
                    "type": "cpu_load",
                    "filter_id": 0x43,  # fcs_pwms消息ID
                    "metric": "peak_load",
                    "description": "电机控制功能峰值负载"
                }
            },
            {
                "logical_function": "LF_Collision_Avoidance",
                "physical_source": {
                    "type": "control_input",
                    "filter_id": 0x46,  # fcs_datafutaba消息ID
                    "metric": "avg_throttle",
                    "description": "遥控输入活动度（避障相关）"
                }
            },
            {
                "logical_function": "LF_Flight_Controller",
                "physical_source": {
                    "type": "gnc_command",
                    "filter_id": 0x44,  # fcs_gncbus消息ID
                    "metric": "cmd_phi_std",
                    "description": "姿态命令变化率"
                }
            },
            {
                "logical_function": "LF_Lidar_Processing",
                "physical_source": {
                    "type": "cpu_load",
                    "filter_id": 0x50,  # lidar性能数据
                    "metric": "avg_load",
                    "description": "LiDAR数据处理CPU负载"
                }
            }
        ]
    
    def _init_edges(self) -> list:
        """
        初始化边配置（功能交互定义）
        
        返回：
            边配置列表，每条边包含：
            - functional_exchange: 功能交换名称
            - source_lf: 源逻辑功能
            - target_lf: 目标逻辑功能
            - physical_source: 物理数据源配置
              - type: 数据类型 (bus_traffic, gnc_command_change, remote_input_activity)
              - filter_id: 过滤ID（消息ID）
              - weight_formula: 权重计算公式
              - description: 描述信息
        """
        return [
            {
                "functional_exchange": "FE_Nav_to_Motor",
                "source_lf": "LF_Navigation",
                "target_lf": "LF_Motor_Control",
                "physical_source": {
                    "type": "bus_traffic",
                    "filter_id": 0x43,  # fcs_pwms
                    "weight_formula": "frequency * size",
                    "description": "导航到电机的PWM通信量"
                }
            },
            {
                "functional_exchange": "FE_Remo_to_Avoid",
                "source_lf": "LF_Collision_Avoidance",
                "target_lf": "LF_Flight_Controller",
                "physical_source": {
                    "type": "remote_input_activity",
                    "filter_id": 0x46,  # fcs_datafutaba
                    "weight_formula": "activity * count",
                    "description": "遥控输入到飞行控制的交互"
                }
            },
            {
                "functional_exchange": "FE_GNC_to_Nav",
                "source_lf": "LF_Flight_Controller",
                "target_lf": "LF_Navigation",
                "physical_source": {
                    "type": "gnc_command_change",
                    "filter_id": 0x44,  # fcs_gncbus
                    "weight_formula": "std",
                    "description": "GN&C命令到导航的交互强度"
                }
            },
            {
                "functional_exchange": "FE_Lidar_to_Avoid",
                "source_lf": "LF_Lidar_Processing",
                "target_lf": "LF_Collision_Avoidance",
                "physical_source": {
                    "type": "bus_traffic",
                    "filter_id": 0x51,  # lidar_obstacles
                    "weight_formula": "count * size",
                    "description": "LiDAR障碍物数据到避障的通信"
                }
            }
        ]
    
    def get_nodes(self) -> list:
        """获取节点配置列表"""
        return self.nodes
    
    def get_edges(self) -> list:
        """获取边配置列表"""
        return self.edges
    
    def add_node(self, logical_function: str, physical_source: dict):
        """
        添加新的节点映射
        
        Args:
            logical_function: 逻辑功能名称
            physical_source: 物理数据源配置
        """
        self.nodes.append({
            "logical_function": logical_function,
            "physical_source": physical_source
        })
    
    def add_edge(self, functional_exchange: str, source_lf: str,
                 target_lf: str, physical_source: dict):
        """
        添加新的边映射
        
        Args:
            functional_exchange: 功能交换名称
            source_lf: 源逻辑功能
            target_lf: 目标逻辑功能
            physical_source: 物理数据源配置
        """
        self.edges.append({
            "functional_exchange": functional_exchange,
            "source_lf": source_lf,
            "target_lf": target_lf,
            "physical_source": physical_source
        })
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "nodes": self.nodes,
            "edges": self.edges
        }
    
    def load_from_dict(self, data: dict):
        """从字典加载配置"""
        if "nodes" in data:
            self.nodes = data["nodes"]
        if "edges" in data:
            self.edges = data["edges"]
    
    def save_to_yaml(self, filepath: str):
        """
        保存配置到YAML文件
        
        Args:
            filepath: 文件路径
        """
        import yaml
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, allow_unicode=True, default_flow_style=False)
    
    def load_from_yaml(self, filepath: str):
        """
        从YAML文件加载配置
        
        Args:
            filepath: 文件路径
        """
        import yaml
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            self.load_from_dict(data)
    
    def print_config(self):
        """打印当前配置"""
        print("=" * 60)
        print("DSM映射配置")
        print("=" * 60)
        print(f"节点数量: {len(self.nodes)}")
        print(f"边数量: {len(self.edges)}")
        print("\n节点列表:")
        for i, node in enumerate(self.nodes):
            print(f"  {i+1}. {node['logical_function']}")
            print(f"     数据源: {node['physical_source']}")
        print("\n边列表:")
        for i, edge in enumerate(self.edges):
            print(f"  {i+1}. {edge['source_lf']} -> {edge['target_lf']}")
            print(f"     交互: {edge['functional_exchange']}")
        print("=" * 60)


# 全局配置实例
config = Config()
mapping_config = MappingConfig()