"""
MiniQGCLinkV2.0 协议解析器（精简版）
处理UDP数据包的接收、解析和错误处理
"""

import asyncio
import logging
from typing import Optional, Callable, Any, Dict

from .nclink_protocol import (
    NCLINK_HEAD0, NCLINK_HEAD1, NCLINK_END0, NCLINK_END1,
    NCLinkProtocolParser,
    PortType
)
# 导入config模块：直接导入（main.py已将src-python添加到sys.path）
from config import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gcs_protocol.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ================================================================
# UDP协议处理器
# ================================================================

class UDPHandler:
    """UDP数据包处理器（多端口支持）"""
    
    def __init__(self, on_message: Optional[Callable[[dict], None]] = None):
        """
        初始化UDP处理器
        
        Args:
            on_message: 消息回调函数
        """
        self.on_message = on_message
        self.parser = NCLinkProtocolParser()
        self._loop: Optional[asyncio.BaseEventLoop] = None
        
        # 多个UDP传输对象（每个端口一个）
        self._transports: Dict[int, asyncio.DatagramTransport] = {}
        self._protocols: Dict[int, NCLinkUDPServerProtocol] = {}
        
        # 从配置加载目标地址
        udp_config = config.get_udp_config()
        self.target_host: str = udp_config.target_ip
        self.target_port: int = udp_config.target_port
        
        logger.info(f"UDP处理器初始化完成 (目标: {self.target_host}:{self.target_port})")
    
    async def start_server(self, host: Optional[str] = None, ports: Optional[list] = None,
                         target_host: Optional[str] = None, target_port: Optional[int] = None):
        """启动UDP服务器
        
        Args:
            host: 绑定地址（默认从配置读取）
            ports: 端口列表（默认从配置读取或使用单端口模式）
            target_host: 目标主机地址（可选，设置发送目标）
            target_port: 目标端口（可选，设置发送目标）
        """
        try:
            # 如果提供了目标地址，更新目标
            if target_host is not None and target_port is not None:
                self.set_target(target_host, target_port)
            
            self._loop = asyncio.get_event_loop()
            
            # 从配置或参数获取监听端口
            udp_config = config.get_udp_config()
            listen_host = host or udp_config.listen_host
            
            # 如果未指定端口列表，使用配置中的监听端口
            if ports is None:
                # 使用配置中的listen_ports，如果不存在则使用默认值
                ports = getattr(udp_config, 'listen_ports', [30509, 18507, 18511])
            
            logger.info(f"监听地址: {listen_host}, 端口列表: {ports}")
            
            for port in ports:
                # 为每个端口创建一个独立的UDP端点
                transport, protocol = await self._loop.create_datagram_endpoint(
                    lambda p=port: NCLinkUDPServerProtocol(self, p),
                    local_addr=(listen_host, port)
                )
                
                self._transports[port] = transport
                self._protocols[port] = protocol
                
                # 根据端口设置对应的端口类型
                if port == 18504:
                    port_type = PortType.PORT_18504_RECEIVE
                elif port == 18506:
                    port_type = PortType.PORT_18506_TELEMETRY
                elif port == 18507:
                    port_type = PortType.PORT_18507_LIDAR
                elif port == 18511:
                    port_type = PortType.PORT_18511_PLANNING
                elif port == 30509:
                    # 测试模式专用端口
                    port_type = PortType.PORT_18506_TELEMETRY  # 视为遥测数据
                else:
                    port_type = PortType.PORT_18504_RECEIVE
                
                protocol.set_port_type(port_type)
                logger.info(f"✓ UDP监听器已启动: {listen_host}:{port} (类型: {port_type.name})")
            
            logger.info(f"✓ 所有UDP服务器已启动，共监听 {len(ports)} 个端口")
            logger.info(f"→ 将发送指令到: {self.target_host}:{self.target_port}")
            
        except Exception as e:
            logger.error(f"✗ 启动UDP服务器失败: {e}")
            raise
    
    def is_running(self):
        """检查UDP服务器是否正在运行"""
        return len(self._transports) > 0
    
    async def stop_server(self):
        """停止所有UDP服务器"""
        logger.info(f"停止UDP服务器，当前运行的端口数量: {len(self._transports)}")
        
        for port, transport in self._transports.items():
            try:
                transport.close()
                logger.info(f"UDP端口 {port} 已关闭")
            except Exception as e:
                logger.error(f"关闭UDP端口 {port} 失败: {e}")
        
        self._transports.clear()
        self._protocols.clear()
        logger.info("所有UDP服务器已停止")
    
    def set_target(self, host: str, port: int):
        """设置目标地址（用于发送指令）
        
        Args:
            host: 目标IP地址
            port: 目标端口
        """
        self.target_host = host
        self.target_port = port
        logger.info(f"UDP目标地址已设置为 {host}:{port}")
    
    def send_data(self, data: bytes, target_host: Optional[str] = None, target_port: Optional[int] = None):
        """发送UDP数据包
        
        Args:
            data: 要发送的数据
            target_host: 目标主机地址（可选，默认使用set_target设置的值）
            target_port: 目标端口（可选，默认使用set_target设置的值）
        """
        host = target_host or self.target_host
        port = target_port or self.target_port
        
        # 检查是否有任何可用的transport
        if not self._transports:
            logger.error(f"没有可用的UDP transport，无法发送数据到 {host}:{port}")
            return
        
        try:
            # 使用任意一个可用的transport发送数据
            # UDP是无连接协议，任何transport都可以发送到任意目标地址
            transport = next(iter(self._transports.values()))
            transport.sendto(data, (host, port))
            logger.info(f"已发送 {len(data)} 字节到 {host}:{port}")
            
            # 打印数据包头部用于调试
            if len(data) >= 10:
                hex_preview = data[:10].hex(' ')
                logger.debug(f"发送数据预览: {hex_preview}")
                
        except Exception as e:
            logger.error(f"发送UDP数据失败: {e}")
    
    def process_data(self, data: bytes, port_type: PortType = PortType.PORT_18504_RECEIVE):
        """处理接收到的数据
        
        Args:
            data: 原始字节数据
            port_type: 端口类型
        """
        try:
            # 使用协议解析器解析数据
            messages = self.parser.feed_data(data, port_type)
            
            # 调用回调函数
            if self.on_message:
                for message in messages:
                    self.on_message(message)
                    
        except Exception as e:
            logger.error(f"处理UDP数据异常: {e}")


# ================================================================
# UDP服务器协议（异步IO）
# ================================================================

class NCLinkUDPServerProtocol(asyncio.DatagramProtocol):
    """NCLink UDP服务器协议（多端口支持）"""
    
    def __init__(self, handler: UDPHandler, port: int):
        super().__init__()
        self.handler = handler
        self.port = port
        self.port_type = PortType.PORT_18504_RECEIVE
        self.loop = asyncio.get_event_loop()
    
    def set_port_type(self, port_type: PortType):
        """设置端口类型"""
        self.port_type = port_type
    
    def connection_made(self, transport):
        """连接建立时调用"""
        self.transport = transport
        logger.info(f"UDP端口 {self.port} 连接已建立 (类型: {self.port_type.name})")
    
    def datagram_received(self, data: bytes, addr):
        """收到UDP数据包的回调"""
        logger.info(f"[端口{self.port}] 收到来自 {addr} 的数据，长度: {len(data)}")
        
        # 打印前10字节用于调试
        hex_preview = data[:10].hex(' ') if len(data) >= 10 else data.hex(' ')
        logger.debug(f"[端口{self.port}] 数据预览: {hex_preview}")
        
        try:
            # 在主事件循环中调用处理函数
            self.loop.call_soon_threadsafe(
                self.handler.process_data,
                data,
                self.port_type
            )
        except Exception as e:
            logger.error(f"[端口{self.port}] 处理UDP数据包失败: {e}")
    
    def error_received(self, exc):
        """错误处理"""
        logger.error(f"[端口{self.port}] UDP错误: {exc}")
    
    def connection_lost(self, exc):
        """连接关闭"""
        if exc:
            logger.error(f"[端口{self.port}] UDP连接丢失: {exc}")
        else:
            logger.info(f"[端口{self.port}] UDP连接已关闭")