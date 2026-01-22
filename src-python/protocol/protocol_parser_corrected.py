"""
修复版NCLink协议解析器 - 协议解析器模块
处理UDP数据包的接收、解析和错误处理
"""

import asyncio
import struct
import logging
from typing import Optional, List, Callable, Any, Dict

from .nclink_protocol import (
    NCLINK_HEAD0, NCLINK_HEAD1, NCLINK_END0, NCLINK_END1,
    BUFFER_SIZE_MAX, NCLinkProtocolParser,
    ExtY_FCS_STATES_T, ExtY_FCS_AVOIFLAG_T, ObstacleOutput_T,
    SystemStatus_T, NCLinkFrame, encode_command_packet,
    encode_takeoff_command, encode_land_command,
    encode_hover_command, encode_rtl_command,
    encode_lidar_avoidance_command, CmdIdx,
    PortType
)
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
    
    async def start_server(self, host: Optional[str] = None, ports: Optional[list] = None):
        """启动UDP服务器
        
        Args:
            host: 绑定地址（默认从配置读取）
            ports: 端口列表（默认从配置读取或使用单端口模式）
        """
        try:
            self._loop = asyncio.get_event_loop()
            
            # 从配置或参数获取监听端口
            udp_config = config.get_udp_config()
            listen_host = host or udp_config.listen_host
            
            # 如果未指定端口列表，使用配置中的监听端口
            if ports is None:
                # 使用配置中的listen_ports，如果不存在则使用默认值
                ports = [18504, 18506, 18507, 18511]
            
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
    
    async def stop_server(self):
        """停止所有UDP服务器"""
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
        
        # 使用端口18504的传输对象发送数据（这是地面站发送指令的端口）
        if 18504 not in self._transports:
            logger.error(f"端口18504未启动，无法发送数据到 {host}:{port}")
            return
        
        try:
            transport = self._transports[18504]
            transport.sendto(data, (host, port))
            logger.debug(f"已发送 {len(data)} 字节数据到 {host}:{port}")
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
            self.handler.process_data(data, self.port_type)
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
# NCLink数据包解析函数
# ================================================================

def parse_nc_link_packet(data: bytes) -> Optional[dict]:
    """
    解析NCLink数据包
    
    Args:
        data: 原始字节数据
        
    Returns:
        解析后的数据字典，失败返回None
    """
    parser = NCLinkProtocolParser()
    messages = parser.feed_data(data)
    
    return messages[0] if messages else None


def validate_nc_link_frame(data: bytes) -> bool:
    """
    验证NCLink帧的有效性
    
    Args:
        data: 原始字节数据
        
    Returns:
        帧是否有效
    """
    if len(data) < 6:
        return False
    
    # 检查帧头
    if data[0] != NCLINK_HEAD0 or data[1] != NCLINK_HEAD1:
        return False
    
    # 提取字段
    data_len = struct.unpack_from('!H', data, 2)[0]
    func_code = data[4]
    payload = data[5:5+data_len]
    checksum = data[5+data_len]
    
    # 验证校验和
    if checksum != NCLinkFrame.calculate_checksum(func_code, payload):
        return False
    
    return True


def get_payload_from_frame(data: bytes) -> Optional[bytes]:
    """
    从NCLink帧中提取有效载荷
    
    Args:
        data: NCLink帧数据
        
    Returns:
        有效载荷，提取失败返回None
    """
    if not validate_nc_link_frame(data):
        return None
    
    data_len = struct.unpack_from('!H', data, 2)[0]
    func_code = data[4]
    return data[5:5+data_len]


# ================================================================
# 辅助函数
# ================================================================

def format_hex_data(data: bytes, max_length: int = 32) -> str:
    """
    格式化十六进制数据（用于调试）
    
    Args:
        data: 字节数据
        max_length: 最大显示长度
        
    Returns:
        格式化后的字符串
    """
    hex_str = data[:max_length].hex(' ')
    if len(data) > max_length:
        hex_str += f"... (共{len(data)}字节)"
    return hex_str


def log_packet_info(message: dict):
    """
    记录数据包信息（用于调试）
    
    Args:
        message: 解析后的消息字典
    """
    func_code = message.get('func_code', 0)
    msg_type = message.get('type', 'unknown')
    data = message.get('data', {})
    
    logger.info(f"数据包类型: {msg_type} (功能码: 0x{func_code:02X})")
    
    if msg_type == 'fcs_states':
        logger.info(f"  位置: ({data.get('latitude', 0):.6f}, {data.get('longitude', 0):.6f}), "
                   f"高度: {data.get('altitude', 0):.1f}m")
        logger.info(f"  姿态: 滚转={data.get('roll', 0):.2f}°, "
                   f"俯仰={data.get('pitch', 0):.2f}°, "
                   f"偏航={data.get('yaw', 0):.2f}°")
    elif msg_type == 'avoiflag':
        logger.info(f"  雷达启用: {data.get('laser_radar_enabled', False)}, "
                   f"避障激活: {data.get('avoidance_flag', False)}")
    elif msg_type == 'system_status':
        logger.info(f"  运行状态: {data.get('is_running', False)}")


# ================================================================
# 测试函数
# ================================================================

async def test_udp_server():
    """测试UDP服务器"""
    handler = UDPHandler(on_message=log_packet_info)
    
    try:
        # 启动服务器
        await handler.start_server(host="0.0.0.0", port=15550)
        
        # 保持运行
        print("UDP服务器运行中，按 Ctrl+C 停止...")
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n收到停止信号")
    except Exception as e:
        print(f"错误: {e}")
    finally:
        await handler.stop_server()


if __name__ == '__main__':
    # 测试帧验证
    frame = NCLinkFrame.create_frame(0x42, b'test_data')
    frame_bytes = frame.to_bytes()
    
    print(f"测试帧: {format_hex_data(frame_bytes)}")
    print(f"帧验证: {validate_nc_link_frame(frame_bytes)}")
    print(f"有效载荷: {get_payload_from_frame(frame_bytes)}")
    
    # 测试UDP服务器（可选）
    # asyncio.run(test_udp_server())