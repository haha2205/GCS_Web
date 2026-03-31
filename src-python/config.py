"""
地面站配置管理
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict


logger = logging.getLogger(__name__)

# 本地测试模式：设置环境变量 GCS_LOCAL_TEST=1 后，Apollo 使用本机唯一网卡IP 192.168.16.13 做同机联调
_LOCAL_TEST = os.getenv("GCS_LOCAL_TEST", "").strip() in ("1", "true", "yes")

FIXED_LISTEN_HOST = "192.168.16.13" if _LOCAL_TEST else "192.168.16.13"
FIXED_LISTEN_PORT = 30509
FIXED_LISTEN_PORTS = [30509, 18511, 18507, 18506]
FIXED_COMMAND_SOURCE_PORT = 18506
FIXED_TARGET_IP = "192.168.16.13" if _LOCAL_TEST else "192.168.16.116"
FIXED_TARGET_PORT = 18504

@dataclass
class UDPConfig:
    """UDP通信配置"""
    # 接收配置（地面站监听）
    listen_host: str = FIXED_LISTEN_HOST
    listen_port: int = FIXED_LISTEN_PORT
    listen_ports: list = field(default_factory=lambda: FIXED_LISTEN_PORTS.copy())
    
    # 发送配置（地面站发送指令到飞控）
    target_ip: str = FIXED_TARGET_IP
    target_port: int = FIXED_TARGET_PORT

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
        """加载固定链路配置，不接受环境变量覆盖。"""
        # 默认监听端口（地面站使用的监听端口）
        # - 30509: 当前实机主聚合接收口
        # - 18511: 规划模块遥测数据
        # - 18507: LiDAR兼容口
        # - 18506: 飞控遥测兼容降级监听口
        # - 30509: 当前实机主聚合接收口，同时作为上行源端口
        self.udp_config.listen_ports = FIXED_LISTEN_PORTS.copy()
        self.udp_config.listen_host = FIXED_LISTEN_HOST
        self.udp_config.listen_port = FIXED_LISTEN_PORT
        
        # 默认发送目标（飞控IP和端口）
        self.udp_config.target_ip = FIXED_TARGET_IP
        self.udp_config.target_port = FIXED_TARGET_PORT
        
        ignored_env_keys = [
            "GCS_LISTEN_PORT",
            "GCS_TARGET_IP",
            "GCS_TARGET_PORT",
        ]
        ignored_env = [key for key in ignored_env_keys if os.getenv(key)]
        if ignored_env:
            logger.warning(
                "检测到网络配置环境变量，但固定链路模式将忽略这些覆盖: %s",
                ", ".join(ignored_env),
            )
    
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
        """固定链路模式下忽略运行时改写请求。"""
        if data:
            logger.warning("忽略运行时UDP配置修改请求，继续使用固定IP与端口配置")

        self.udp_config.listen_host = FIXED_LISTEN_HOST
        self.udp_config.listen_port = FIXED_LISTEN_PORT
        self.udp_config.listen_ports = FIXED_LISTEN_PORTS.copy()
        self.udp_config.target_ip = FIXED_TARGET_IP
        self.udp_config.target_port = FIXED_TARGET_PORT
    
    def print_config(self):
        """打印当前配置"""
        print("=" * 60)
        print("地面站配置信息")
        print("=" * 60)
        print(f"接收配置: {self.udp_config.listen_host}:{self.udp_config.listen_port}")
        print(f"监听端口列表: {self.udp_config.listen_ports}")
        print(f"发送目标: {self.udp_config.target_ip}:{self.udp_config.target_port}")
        print("=" * 60)


config = Config()