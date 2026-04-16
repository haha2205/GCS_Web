"""
MiniQGCLinkV2.0 协议解析器（精简版）
处理UDP数据包的接收、解析和错误处理
"""

import asyncio
import logging
import socket
import time
from typing import Optional, Callable, Any, Dict, List

from .nclink_protocol import (
    NCLINK_HEAD0, NCLINK_HEAD1, NCLINK_END0, NCLINK_END1,
    NCLinkProtocolParser,
    PortType,
)
# 导入config模块：直接导入（main.py已将src-python添加到sys.path）
from config import config, FIXED_COMMAND_SOURCE_PORT

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


class _RollingTrafficWindow:
    def __init__(self, window_seconds: int = 10):
        self.window_seconds = max(1, int(window_seconds))
        self._overall: Dict[int, Dict[str, int]] = {}
        self._by_key: Dict[str, Dict[int, Dict[str, int]]] = {}

    def add(self, key: Optional[str], payload_bytes: int, frame_bytes: int, packets: int = 1) -> None:
        now_sec = int(time.monotonic())
        self._add_bucket(self._overall, now_sec, packets, payload_bytes, frame_bytes)
        if key:
            self._add_bucket(self._by_key.setdefault(key, {}), now_sec, packets, payload_bytes, frame_bytes)
        self._prune(now_sec)

    def snapshot(self) -> Dict[str, Any]:
        now_sec = int(time.monotonic())
        self._prune(now_sec)
        cutoff = now_sec - self.window_seconds + 1
        by_key: Dict[str, Dict[str, Any]] = {}
        for key, buckets in sorted(self._by_key.items()):
            summary = self._summarize(buckets, cutoff)
            if summary['packets'] > 0:
                by_key[key] = self._build_rate_snapshot(summary)
        return {
            'window_seconds': self.window_seconds,
            'overall': self._build_rate_snapshot(self._summarize(self._overall, cutoff)),
            'by_key': by_key,
        }

    def _add_bucket(
        self,
        container: Dict[int, Dict[str, int]],
        second_key: int,
        packets: int,
        payload_bytes: int,
        frame_bytes: int,
    ) -> None:
        bucket = container.setdefault(second_key, {'packets': 0, 'payload_bytes': 0, 'frame_bytes': 0})
        bucket['packets'] += int(packets)
        bucket['payload_bytes'] += max(0, int(payload_bytes))
        bucket['frame_bytes'] += max(0, int(frame_bytes))

    def _summarize(self, buckets: Dict[int, Dict[str, int]], cutoff: int) -> Dict[str, int]:
        summary = {'packets': 0, 'payload_bytes': 0, 'frame_bytes': 0}
        for second_key, values in buckets.items():
            if second_key < cutoff:
                continue
            summary['packets'] += values['packets']
            summary['payload_bytes'] += values['payload_bytes']
            summary['frame_bytes'] += values['frame_bytes']
        return summary

    def _build_rate_snapshot(self, summary: Dict[str, int]) -> Dict[str, Any]:
        duration = float(self.window_seconds)
        return {
            'packets': summary['packets'],
            'payload_bytes': summary['payload_bytes'],
            'frame_bytes': summary['frame_bytes'],
            'pps': round(summary['packets'] / duration, 3),
            'payload_kbps': round((summary['payload_bytes'] * 8.0) / 1000.0 / duration, 3),
            'frame_kbps': round((summary['frame_bytes'] * 8.0) / 1000.0 / duration, 3),
        }

    def _prune(self, now_sec: int) -> None:
        cutoff = now_sec - self.window_seconds + 1
        self._prune_bucket_map(self._overall, cutoff)
        for key in list(self._by_key.keys()):
            buckets = self._by_key[key]
            self._prune_bucket_map(buckets, cutoff)
            if not buckets:
                del self._by_key[key]

    @staticmethod
    def _prune_bucket_map(buckets: Dict[int, Dict[str, int]], cutoff: int) -> None:
        for second_key in [key for key in buckets.keys() if key < cutoff]:
            del buckets[second_key]


class RuntimeTrafficMonitor:
    def __init__(self, window_seconds: int = 10):
        self.started_at = time.monotonic()
        self.window_seconds = window_seconds
        self._rx_window = _RollingTrafficWindow(window_seconds)
        self._tx_window = _RollingTrafficWindow(window_seconds)
        self._parsed_window = _RollingTrafficWindow(window_seconds)
        self._reject_window = _RollingTrafficWindow(window_seconds)
        self._issue_window = _RollingTrafficWindow(window_seconds)
        self.rx_totals = {'packets': 0, 'payload_bytes': 0}
        self.tx_totals = {'packets': 0, 'payload_bytes': 0}
        self.parsed_totals = {'messages': 0, 'payload_bytes': 0, 'frame_bytes': 0}
        self.rejected_total = 0
        self.issue_total = 0
        self.rx_by_port: Dict[str, Dict[str, int]] = {}
        self.tx_by_source_port: Dict[str, Dict[str, int]] = {}
        self.tx_by_target: Dict[str, Dict[str, int]] = {}
        self.parsed_by_type: Dict[str, Dict[str, int]] = {}
        self.rejected_by_reason: Dict[str, int] = {}
        self.issues_by_reason: Dict[str, int] = {}

    def record_rx_datagram(self, local_port: int, size: int) -> None:
        key = str(local_port)
        self.rx_totals['packets'] += 1
        self.rx_totals['payload_bytes'] += size
        self._bump_counter(self.rx_by_port, key, packets=1, payload_bytes=size)
        self._rx_window.add(key, size, size)

    def record_tx_packet(self, source_port: Optional[int], target_host: str, target_port: int, size: int) -> None:
        self.tx_totals['packets'] += 1
        self.tx_totals['payload_bytes'] += size
        source_key = str(source_port) if source_port is not None else 'unknown'
        target_key = f'{target_host}:{target_port}'
        self._bump_counter(self.tx_by_source_port, source_key, packets=1, payload_bytes=size)
        self._bump_counter(self.tx_by_target, target_key, packets=1, payload_bytes=size)
        self._tx_window.add(target_key, size, size)

    def record_parsed_message(self, message: dict) -> None:
        msg_type = str(message.get('type') or 'unknown')
        payload_size = int(message.get('payload_size', 0) or 0)
        frame_size = int(message.get('frame_size', payload_size) or payload_size)
        self.parsed_totals['messages'] += 1
        self.parsed_totals['payload_bytes'] += payload_size
        self.parsed_totals['frame_bytes'] += frame_size
        self._bump_counter(self.parsed_by_type, msg_type, packets=1, payload_bytes=payload_size, frame_bytes=frame_size)
        self._parsed_window.add(msg_type, payload_size, frame_size)

    def record_parser_rejection(self, reason: str, frame_size: int = 0) -> None:
        self.rejected_total += 1
        self.rejected_by_reason[reason] = self.rejected_by_reason.get(reason, 0) + 1
        self._reject_window.add(reason, 0, frame_size)

    def record_parser_issue(self, reason: str, frame_size: int = 0) -> None:
        self.issue_total += 1
        self.issues_by_reason[reason] = self.issues_by_reason.get(reason, 0) + 1
        self._issue_window.add(reason, 0, frame_size)

    def snapshot(self) -> Dict[str, Any]:
        return {
            'window_seconds': self.window_seconds,
            'uptime_sec': round(max(0.0, time.monotonic() - self.started_at), 3),
            'rx_datagrams': {
                'packets_total': self.rx_totals['packets'],
                'payload_bytes_total': self.rx_totals['payload_bytes'],
                'recent': self._rx_window.snapshot(),
                'by_port_total': self.rx_by_port,
            },
            'tx_packets': {
                'packets_total': self.tx_totals['packets'],
                'payload_bytes_total': self.tx_totals['payload_bytes'],
                'recent': self._tx_window.snapshot(),
                'by_source_port_total': self.tx_by_source_port,
                'by_target_total': self.tx_by_target,
            },
            'parsed_messages': {
                'messages_total': self.parsed_totals['messages'],
                'payload_bytes_total': self.parsed_totals['payload_bytes'],
                'frame_bytes_total': self.parsed_totals['frame_bytes'],
                'recent': self._parsed_window.snapshot(),
                'by_type_total': self.parsed_by_type,
            },
            'parser_rejections': {
                'total': self.rejected_total,
                'by_reason_total': self.rejected_by_reason,
                'recent': self._reject_window.snapshot(),
            },
            'parser_issues': {
                'total': self.issue_total,
                'by_reason_total': self.issues_by_reason,
                'recent': self._issue_window.snapshot(),
            },
        }

    @staticmethod
    def _bump_counter(
        container: Dict[str, Dict[str, int]],
        key: str,
        *,
        packets: int = 0,
        payload_bytes: int = 0,
        frame_bytes: int = 0,
    ) -> None:
        counter = container.setdefault(key, {'packets': 0, 'payload_bytes': 0, 'frame_bytes': 0})
        counter['packets'] += packets
        counter['payload_bytes'] += payload_bytes
        counter['frame_bytes'] += frame_bytes


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
        self._loop: Optional[asyncio.BaseEventLoop] = None
        
        # 多个UDP传输对象（每个端口一个）
        self._transports: Dict[int, asyncio.DatagramTransport] = {}
        self._protocols: Dict[int, NCLinkUDPServerProtocol] = {}
        self.runtime_monitor = RuntimeTrafficMonitor()
        
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
                ports = getattr(udp_config, 'listen_ports', [30509, 18511, 18507, 18506])
            
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
                    # 当前实机主聚合接收口：飞控业务遥测与心跳回执统一从这里进入
                    port_type = PortType.PORT_18506_TELEMETRY
                else:
                    port_type = PortType.PORT_18504_RECEIVE
                
                protocol.set_port_type(port_type)
                logger.info(f"[OK] UDP监听器已启动: {listen_host}:{port} (类型: {port_type.name})")

                if port == 30509:
                    logger.info(f"[OK] 已确认 {listen_host}:{port} 为当前实机主聚合接收口")
                elif port == 18506:
                    logger.info(f"[OK] 已确认 {listen_host}:{port} 仅保留为飞控遥测兼容降级监听口")
            
            logger.info(f"[OK] 所有UDP服务器已启动，共监听 {len(ports)} 个端口")
            logger.info(f"→ 将发送指令到: {self.target_host}:{self.target_port}")
            
        except Exception as e:
            logger.error(f"[ERR] 启动UDP服务器失败: {e}")
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

        if not self._transports:
            logger.error(f"没有可用的UDP transport，无法发送数据到 {host}:{port}")
            return
        
        try:
            transport = self._transports.get(FIXED_COMMAND_SOURCE_PORT)
            if transport is None:
                listen_port = config.get_udp_config().listen_port
                transport = self._transports.get(listen_port)
            if transport is None:
                transport = next(iter(self._transports.values()))

            transport.sendto(data, (host, port))
            sockname = transport.get_extra_info('sockname')
            source_port = sockname[1] if isinstance(sockname, tuple) and len(sockname) > 1 else None
            self.runtime_monitor.record_tx_packet(source_port, host, port, len(data))
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
            # 保留兼容入口，UDP 场景下实际解析在各端口协议实例内完成。
            messages = NCLinkProtocolParser().feed_data(data, port_type)
            self.dispatch_messages(messages)
        except Exception as e:
            logger.error(f"处理UDP数据异常: {e}")

    def dispatch_messages(self, messages: List[dict]) -> None:
        """分发已解析消息。"""
        if not self.on_message or not messages:
            return

        for message in messages:
            self.on_message(message)

    def get_runtime_stats(self) -> Dict[str, Any]:
        stats = self.runtime_monitor.snapshot()
        stats['is_running'] = self.is_running()
        stats['listening_ports'] = sorted(self._transports.keys())
        return stats


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
        # UDP 端口之间不能共享帧缓冲状态，避免多端口数据交叉污染。
        self.parser = NCLinkProtocolParser(on_event=self._handle_parser_event)
    
    def set_port_type(self, port_type: PortType):
        """设置端口类型"""
        self.port_type = port_type
    
    def connection_made(self, transport):
        """连接建立时调用"""
        self.transport = transport
        sock = transport.get_extra_info('socket')
        if sock is not None:
            try:
                # Increase the UDP receive buffer to reduce packet drops under sustained high-rate telemetry.
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
                actual_size = sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
                logger.info(f"UDP端口 {self.port} 接收缓冲区已设置为 {actual_size} 字节")
            except OSError as exc:
                logger.warning(f"UDP端口 {self.port} 设置接收缓冲区失败: {exc}")
        logger.info(f"UDP端口 {self.port} 连接已建立 (类型: {self.port_type.name})")
    
    def datagram_received(self, data: bytes, addr):
        """收到UDP数据包的回调"""
        logger.debug(f"[端口{self.port}] 收到来自 {addr} 的数据，长度: {len(data)}")
        self.handler.runtime_monitor.record_rx_datagram(self.port, len(data))

        # 打印前10字节用于调试（兼容Python 3.7）
        import binascii
        preview_data = data[:10] if len(data) >= 10 else data
        hex_preview = binascii.hexlify(preview_data).decode('ascii')
        hex_preview = ' '.join([hex_preview[i:i+2] for i in range(0, len(hex_preview), 2)])
        logger.debug(f"[端口{self.port}] 数据预览: {hex_preview}")
        
        try:
            messages = self.parser.feed_data(data, self.port_type)
            self.handler.dispatch_messages(messages)
        except Exception as e:
            logger.error(f"[端口{self.port}] 处理UDP数据包失败: {e}")

    def _handle_parser_event(self, event: dict) -> None:
        event_type = str(event.get('type') or '')
        if event_type == 'message_parsed':
            message = event.get('message')
            if isinstance(message, dict):
                self.handler.runtime_monitor.record_parsed_message(message)
            return

        if event_type == 'frame_rejected':
            reason = str(event.get('reason') or 'unknown')
            frame_size = int(event.get('frame_size', 0) or 0)
            self.handler.runtime_monitor.record_parser_rejection(reason, frame_size)
            return

        if event_type == 'frame_issue':
            reason = str(event.get('reason') or 'unknown')
            frame_size = int(event.get('frame_size', 0) or 0)
            self.handler.runtime_monitor.record_parser_issue(reason, frame_size)
    
    def error_received(self, exc):
        """错误处理"""
        logger.error(f"[端口{self.port}] UDP错误: {exc}")
    
    def connection_lost(self, exc):
        """连接关闭"""
        if exc:
            logger.error(f"[端口{self.port}] UDP连接丢失: {exc}")
        else:
            logger.info(f"[端口{self.port}] UDP连接已关闭")


