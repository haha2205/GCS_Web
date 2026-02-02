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
    listen_host: str = "192.168.16.13"
    listen_port: int = 30509
    listen_ports: list = field(default_factory=lambda: [30509, 18507, 18511])
    
    # 发送配置（地面站发送指令到飞控）
    target_ip: str = "192.168.16.116"
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
        # - 18511: 接收规划模块遥测数据
        self.udp_config.listen_ports = [30509, 18507, 18511]  # ✅ 修复：包含三个端口
        self.udp_config.listen_host = "192.168.16.13"
        self.udp_config.listen_port = 30509
        
        # 默认发送目标（飞控IP和端口）
        # 127.0.0.1:18504（默认本地测试）
        self.udp_config.target_ip = "192.168.16.116"
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
        print(f"监听端口列表: {self.udp_config.listen_ports}")
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
        基于MDC610架构：
        - SoC: 感知(Perception), 规划(Planning), 通信(Comm)
        - MCU GP4: 遥控解析(RC_Parser), 惯导解析(INS_Parser)
        - MCU GP2: 飞控(FCS), SoC通信适配(SoC_Adapter)
        - MCU GP3: 电机驱动(Motor_Driver)
        """
        return [
            # --- SoC Partition ---
            {
                "logical_function": "LF_Perception",
                "physical_source": {
                    "type": "cpu_load",
                    "filter_id": 0x51,  # LIDAR_OBSTACLE_INFO (感知结果)
                    "metric": "avg_load",
                    "description": "雷达/感知模块 (SoC)"
                }
            },
            {
                "logical_function": "LF_Path_Planning",
                "physical_source": {
                    "type": "planning_telemetry",
                    # 假设 0x71 是规划遥测 (GCS_TELEMETRY)
                    "filter_id": 0x71,  
                    "metric": "avg_cpu",
                    "description": "路径规划模块 (SoC)"
                }
            },
            {
                "logical_function": "LF_Communication",
                "physical_source": {
                    "type": "traffic_volume",
                    "filter_id": 0x46,  # DATAGCS (作为通信量参考)
                    "metric": "total_bytes",
                    "description": "通信管理模块 (SoC)"
                }
            },
            
            # --- MCU GP4 Partition ---
            {
                "logical_function": "LF_RC_Parser",
                "physical_source": {
                    "type": "control_input",
                    "filter_id": 0x43,  # DATACTRL (解析后的控制指令)
                    "metric": "activity",
                    "description": "遥控器解析 (MCU GP4)"
                }
            },
            {
                "logical_function": "LF_INS_Parser",
                "physical_source": {
                    "type": "gnc_state",
                    "filter_id": 0x42,  # STATES (惯导解算结果)
                    "metric": "frequency",
                    "description": "惯导解析 (MCU GP4)"
                }
            },
            
            # --- MCU GP2 Partition ---
            {
                "logical_function": "LF_Flight_Control",
                "physical_source": {
                    "type": "gnc_command",
                    "filter_id": 0x44,  # GNCBUS (飞控核心计算)
                    "metric": "complexity",
                    "description": "飞行控制 (MCU GP2)"
                }
            },
            {
                "logical_function": "LF_SoC_Adapter",
                "physical_source": {
                    "type": "bus_traffic",
                    "filter_id": 0x44,  # GNCBUS (SoC交互数据)
                    "metric": "throughput",
                    "description": "SoC通信适配 (MCU GP2)"
                }
            },

            # --- MCU GP3 Partition ---
            {
                "logical_function": "LF_Motor_Driver",
                "physical_source": {
                    "type": "actuator_output",
                    "filter_id": 0x41,  # PWMS (驱动输出)
                    "metric": "channel_count",
                    "description": "电机驱动 (MCU GP3)"
                }
            }
        ]
    
    def _init_edges(self) -> list:
        """
        初始化边配置（功能交互定义）
        反映MDC610内部及模块间的数据流
        """
        return [
            # 1. GP4 -> GP2 (RC -> FCS)
            {
                "functional_exchange": "FE_RC_Data",
                "source_lf": "LF_RC_Parser",
                "target_lf": "LF_Flight_Control",
                "physical_source": {
                    "type": "bus_traffic",
                    "filter_id": 0x43,  # DATACTRL
                    "weight_formula": "frequency * size",
                    "description": "遥控指令流 (GP4->GP2)"
                }
            },
            # 2. GP4 -> GP2 (INS -> FCS)
            {
                "functional_exchange": "FE_Nav_State",
                "source_lf": "LF_INS_Parser",
                "target_lf": "LF_Flight_Control",
                "physical_source": {
                    "type": "bus_traffic",
                    "filter_id": 0x42,  # STATES
                    "weight_formula": "frequency * size * 2", # 高频关键数据
                    "description": "惯导状态流 (GP4->GP2)"
                }
            },
            # 3. SoC -> GP2 (Planning -> FCS)
            # 物理路径: SoC Planning -> SoC Comm -> GP2 Adapter -> GP2 FCS
            # 逻辑简化: Planning -> FCS
            {
                "functional_exchange": "FE_Trajectory_Cmd",
                "source_lf": "LF_Path_Planning",
                "target_lf": "LF_Flight_Control",
                "physical_source": {
                    "type": "gnc_command_change",
                    "filter_id": 0x44,  # GNCBUS
                    "weight_formula": "std * 10", # 变化率代表交互强度
                    "description": "轨迹指令流 (SoC->GP2)"
                }
            },
            # 4. SoC Internal (Perception -> Planning)
            {
                "functional_exchange": "FE_Obstacles",
                "source_lf": "LF_Perception",
                "target_lf": "LF_Path_Planning",
                "physical_source": {
                    "type": "bus_traffic",
                    "filter_id": 0x51,  # OBSTACLE_INFO
                    "weight_formula": "count * size",
                    "description": "感知障碍物数据 (SoC内部)"
                }
            },
            # 5. GP2 -> GP3 (FCS -> Motor)
            {
                "functional_exchange": "FE_Motor_PWM",
                "source_lf": "LF_Flight_Control",
                "target_lf": "LF_Motor_Driver",
                "physical_source": {
                    "type": "bus_traffic",
                    "filter_id": 0x41,  # PWMS
                    "weight_formula": "frequency * size",
                    "description": "电机控制信号 (GP2->GP3)"
                }
            },
            # 6. SoC Internal (Comm -> Planning/Perception) - 
            # 这里定义反向链路，比如地面站指令上传
            {
                "functional_exchange": "FE_GCS_Uplink",
                "source_lf": "LF_Communication",
                "target_lf": "LF_Path_Planning",
                "physical_source": {
                    "type": "bus_traffic",
                    "filter_id": 0x70, # GCS_COMMAND
                    "weight_formula": "count * size",
                    "description": "地面站上行指令 (SoC Comm->Planning)"
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