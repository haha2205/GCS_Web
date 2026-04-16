"""
WebSocket 连接管理器
负责将UDP解析的数据实时推送到前端Vue应用
"""

import asyncio
import json
import logging
from typing import Dict, Optional, Set
from fastapi import WebSocket
from fastapi.websockets import WebSocketState

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    WebSocket连接管理器
    维护所有活跃的WebSocket连接并广播消息。
    
    设计原则：
    - UDP 数据链路完全独立于 WebSocket 连接生命周期
    - 前端刷新/重连不会影响后端 UDP 接收和解析
    - 连接断开时静默清理，不产生级联错误
    """
    
    def __init__(self):
        # 存储所有活跃的WebSocket连接
        self.active_connections: Set[WebSocket] = set()
        self._snapshot_messages: Dict[str, dict] = {}
        self._pending_latest_messages: Dict[str, dict] = {}
        self._latest_broadcast_task: Optional[asyncio.Task] = None
        self._broadcast_error_count = 0  # 连续广播错误计数
        self._max_consecutive_errors = 50  # 超过此阈值打印告警
        self._send_timeout_seconds = 0.25
    
    async def connect(self, websocket: WebSocket):
        """接受新的WebSocket连接"""
        await websocket.accept()
        self.active_connections.add(websocket)
        self._broadcast_error_count = 0  # 重置错误计数
        
        logger.info(f"WebSocket客户端已连接, 当前连接数: {len(self.active_connections)}")
        
        # 发送欢迎消息
        await self.send_personal_message({
            "type": "system",
            "message": "WebSocket连接已建立",
            "status": "connected",
            "timestamp": 0
        }, websocket)

        await self.send_cached_messages(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接（静默，无级联影响）"""
        if websocket in self.active_connections:
            self.active_connections.discard(websocket)
            logger.info(f"WebSocket客户端已断开, 当前连接数: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """向特定客户端发送消息"""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                payload = json.dumps(message, ensure_ascii=False, separators=(',', ':'))
                await asyncio.wait_for(websocket.send_text(payload), timeout=self._send_timeout_seconds)
        except Exception as e:
            logger.debug(f"发送个人消息失败(客户端可能已刷新): {e}")
            self.disconnect(websocket)

    def cache_message(self, message: dict, cache_key: str):
        """缓存最新状态, 供新连接建立后回放当前快照。"""
        if not cache_key:
            return

        self._snapshot_messages[cache_key] = dict(message)

    async def send_cached_messages(self, websocket: WebSocket):
        """按稳定顺序向新连接补发最近一次状态快照。"""
        if not self._snapshot_messages:
            return

        preferred_order = [
            'config_update:connection',
            'config_update:log',
            'udp_status_change',
            'recording_status',
            'udp_data:fcs_states',
            'udp_data:fcs_pwms',
            'udp_data:fcs_datactrl',
            'udp_data:fcs_gncbus',
            'udp_data:avoiflag',
            'udp_data:fcs_datafutaba',
            'udp_data:fcs_datagcs',
            'udp_data:fcs_param',
            'udp_data:planning_telemetry',
            'udp_data:fcs_esc',
        ]

        sent_keys = set()
        for cache_key in preferred_order:
            payload = self._snapshot_messages.get(cache_key)
            if payload:
                await self.send_personal_message(payload, websocket)
                sent_keys.add(cache_key)

        for cache_key, payload in self._snapshot_messages.items():
            if cache_key in sent_keys:
                continue
            await self.send_personal_message(payload, websocket)
    
    async def broadcast(self, message: dict):
        """向所有连接的客户端广播消息（容错：单个连接异常不影响其他连接）"""
        if not self.active_connections:
            return

        # 复制连接集合,避免迭代时修改
        connections = list(self.active_connections)
        disconnected = []
        payload = json.dumps(message, ensure_ascii=False, separators=(',', ':'))

        async def _send_to_connection(websocket: WebSocket):
            if websocket.client_state != WebSocketState.CONNECTED:
                return websocket

            try:
                await asyncio.wait_for(websocket.send_text(payload), timeout=self._send_timeout_seconds)
                return None
            except Exception as e:
                logger.debug(f"广播写入失败(客户端可能已刷新): {e}")
                return websocket

        results = await asyncio.gather(*[_send_to_connection(websocket) for websocket in connections], return_exceptions=True)
        for result in results:
            if isinstance(result, WebSocket):
                disconnected.append(result)
            elif isinstance(result, Exception):
                logger.debug(f"广播任务执行异常: {result}")

        # 批量清理断开的连接
        for ws in disconnected:
            self.active_connections.discard(ws)
        
        if disconnected:
            self._broadcast_error_count += len(disconnected)
            if self._broadcast_error_count > self._max_consecutive_errors:
                logger.warning(
                    f"WebSocket 连续广播异常累计 {self._broadcast_error_count} 次, "
                    f"当前活跃连接: {len(self.active_connections)}"
                )
                self._broadcast_error_count = 0
        else:
            self._broadcast_error_count = 0

    def schedule_latest_broadcast(self, message: dict, cache_key: str):
        """对高频遥测只保留每类最新一条，避免广播任务积压。"""
        if not cache_key:
            asyncio.create_task(self.broadcast(message))
            return

        self._pending_latest_messages[cache_key] = dict(message)
        if self._latest_broadcast_task is None or self._latest_broadcast_task.done():
            self._latest_broadcast_task = asyncio.create_task(self._flush_latest_broadcasts())

    async def _flush_latest_broadcasts(self):
        while self._pending_latest_messages:
            pending_messages = list(self._pending_latest_messages.values())
            self._pending_latest_messages.clear()
            await asyncio.gather(*(self.broadcast(message) for message in pending_messages))

        self._latest_broadcast_task = None
    
    async def broadcast_telemetry(self, message: dict):
        """
        广播遥测数据
        特殊处理遥测数据,避免消息过多导致阻塞
        """
        # 只连接数量大于0时才发送
        if self.active_connections:
            await self.broadcast(message)
    
    async def broadcast_flight_state(self, state: dict):
        """广播飞行状态"""
        await self.broadcast({
            "type": "flight_state",
            "data": state
        })
    
    async def broadcast_obstacle(self, obstacle_data: dict):
        """广播障碍物检测数据"""
        await self.broadcast({
            "type": "obstacles",
            "data": obstacle_data
        })
    
    async def broadcast_system_status(self, status: dict):
        """广播系统状态"""
        await self.broadcast({
            "type": "system_status",
            "data": status
        })
    
    def get_connection_count(self) -> int:
        """获取当前连接数量"""
        return len(self.active_connections)
    
    def is_empty(self) -> bool:
        """检查是否有活跃连接"""
        return len(self.active_connections) == 0


# 全局WebSocket管理器实例
manager = WebSocketManager()