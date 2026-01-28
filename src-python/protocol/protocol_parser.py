"""
MiniQGCLinkV2.0 协议解析器（精简版）
处理UDP数据包的接收、解析和错误处理
"""

import asyncio
import logging
from typing import Optional, Callable, Any, Dict, List
import struct

from .nclink_protocol import (
    NCLINK_HEAD0, NCLINK_HEAD1, NCLINK_END0, NCLINK_END1,
    NCLinkProtocolParser,
    PortType,
    NCLINK_GCS_TELEMETRY,  # 导入功能码常量
    GCSTelemetry_T,        # 导入遥测数据结构体
)
from .lidar_imu_protocol import (
    NCLINK_RECEIVE_LIDAR_OBSTACLES, # 导入雷达功能码
    ObstacleOutput_T       # 导入雷达数据结构体
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

            # 打印数据包头部用于调试（兼容Python 3.7）
            if len(data) >= 10:
                import binascii
                hex_bytes = binascii.hexlify(data[:10]).decode('ascii')
                hex_preview = ' '.join([hex_bytes[i:i+2] for i in range(0, len(hex_bytes), 2)])
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

        # 打印前10字节用于调试（兼容Python 3.7）
        import binascii
        preview_data = data[:10] if len(data) >= 10 else data
        hex_preview = binascii.hexlify(preview_data).decode('ascii')
        hex_preview = ' '.join([hex_preview[i:i+2] for i in range(0, len(hex_preview), 2)])
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


# ================================================================
# 协议解析器
# ================================================================

class NCLinkFrame:
    """NCLink 帧结构"""
    
    @staticmethod
    def calculate_checksum(func_code: int, payload: bytes) -> int:
        """计算校验和"""
        # 校验和算法：帧头(2) + 功能码(1) + 数据长度(2) + 数据区间
        checksum = 0
        for b in payload:
            checksum ^= b
        return checksum
    
    def parse_frame(self, frame_data: bytes, port_type: PortType) -> Optional[dict]:
        """解析单个帧
        
        Args:
            frame_data: 帧数据
            port_type: 端口类型
        
        Returns:
            解析后的消息字典，失败返回None
        """
        logger.debug(f"[parse_frame] 帧数据长度: {len(frame_data)}")
        logger.debug(f"[parse_frame] 帧数据预览: {frame_data[:20].hex(' ')}")

        if len(frame_data) < 8:
            logger.error(f"[parse_frame] 帧数据长度不足: {len(frame_data)} < 8")
            return None

        if frame_data[0] != NCLINK_HEAD0 or frame_data[1] != NCLINK_HEAD1:
            logger.error(f"[parse_frame] 帧头无效: {frame_data[:2].hex(' ')}")
            return None

        func_code = frame_data[2]
        data_len = struct.unpack_from('!H', frame_data, 3)[0]
        expected_frame_len = 2 + 1 + 2 + data_len + 1 + 2

        if len(frame_data) < expected_frame_len:
            logger.error(f"[parse_frame] 帧数据长度不足: {len(frame_data)} < {expected_frame_len}")
            return None

        payload = frame_data[5:5 + data_len]
        checksum = frame_data[5 + data_len]
        calculated_checksum = self.calculate_checksum(func_code, payload)

        if checksum != calculated_checksum:
            logger.error(f"[parse_frame] 校验和错误: 接收=0x{checksum:02X}, 计算=0x{calculated_checksum:02X}")
            return None

        logger.info(f"[parse_frame] 功能码: 0x{func_code:02X}, 数据长度: {data_len}, 校验和: 0x{checksum:02X}")

        if func_code == NCLINK_GCS_TELEMETRY:
            telemetry = GCSTelemetry_T.from_bytes(payload)
            if telemetry:
                logger.debug(f"[parse_frame] 规划遥测解析成功")
                # 将对象转换为字典，添加type字段方便后续处理
                result = telemetry.to_dict() if hasattr(telemetry, 'to_dict') else telemetry.__dict__
                result['type'] = 'planning_telemetry'
                result['func_code'] = func_code
                return result
            else:
                logger.error("[parse_frame] 遥测数据解析失败")
        
        elif func_code == NCLINK_RECEIVE_LIDAR_OBSTACLES:
            obstacles = ObstacleOutput_T.from_bytes(payload)
            if obstacles:
                logger.debug(f"[parse_frame] 雷达障碍物解析成功: {obstacles.obstacle_count}个")
                result = obstacles.to_dict() if hasattr(obstacles, 'to_dict') else obstacles.__dict__
                result['type'] = 'lidar_obstacles'
                result['func_code'] = func_code
                return result
            else:
                logger.error("[parse_frame] 雷达障碍物解析失败")

        return None
    
    def feed_data(self, data: bytes, port_type: PortType = PortType.PORT_18504_RECEIVE) -> List[dict]:
        """feeding数据并解析
        
        Args:
            data: 接收到的字节数据
            port_type: 端口类型（用于区分不同来源的数据）
        
        Returns:
            解析后的消息列表
        """
        logger.debug(f"[feed_data] 接收到数据长度: {len(data)} 字节")
        logger.debug(f"[feed_data] 数据预览: {data[:20].hex(' ')}")

        self.buffer.extend(data)
        messages = []

        while len(self.buffer) >= 6:  # 最小帧长度
            logger.debug(f"[feed_data] 当前缓冲区长度: {len(self.buffer)}")
            logger.debug(f"[feed_data] 缓冲区预览: {self.buffer[:20].hex(' ')}")

            # 检查帧头
            if self.buffer[0] != NCLINK_HEAD0 or self.buffer[1] != NCLINK_HEAD1:
                logger.warning(f"[feed_data] 无效帧头: {self.buffer[:2].hex(' ')}")
                self.buffer.pop(0)
                continue

            # 检查帧长度
            if len(self.buffer) < 8:
                logger.debug("[feed_data] 缓冲区数据不足以解析帧头")
                break

            func_code = self.buffer[2]
            data_len = struct.unpack_from('!H', self.buffer, 3)[0]
            expected_frame_len = 2 + 1 + 2 + data_len + 1 + 2

            if len(self.buffer) < expected_frame_len:
                logger.debug(f"[feed_data] 缓冲区数据不足以解析完整帧: {len(self.buffer)} < {expected_frame_len}")
                break

            frame_data = self.buffer[:expected_frame_len]
            self.buffer = self.buffer[expected_frame_len:]

            logger.info(f"[feed_data] 解析帧: 功能码=0x{func_code:02X}, 数据长度={data_len}, 帧长度={expected_frame_len}")

            # 调用parse_frame解析帧
            message = self.parse_frame(frame_data, port_type)
            if message:
                messages.append(message)

        return messages