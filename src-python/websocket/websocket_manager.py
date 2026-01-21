"""
WebSocket 连接管理器
负责将UDP解析的数据实时推送到前端Vue应用
"""

import json
import logging
from typing import Set
from fastapi import WebSocket
from fastapi.websockets import WebSocketState

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    WebSocket连接管理器
    维护所有活跃的WebSocket连接并广播消息
    """
    
    def __init__(self):
        # 存储所有活跃的WebSocket连接
        self.active_connections: Set[WebSocket] = set()
        self._message_queue = []
    
    async def connect(self, websocket: WebSocket):
        """接受新的WebSocket连接"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket客户端已连接, 当前连接数: {len(self.active_connections)}")
        
        # 发送欢迎消息
        await self.send_personal_message({
            "type": "system",
            "message": "WebSocket连接已建立",
            "status": "connected",
            "timestamp": 0
        }, websocket)
    
    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket客户端已断开, 当前连接数: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """向特定客户端发送消息"""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
        except Exception as e:
            logger.error(f"发送个人消息失败: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """向所有连接的客户端广播消息"""
        if not self.active_connections:
            return
        
        # 复制连接集合,避免迭代时修改
        connections = self.active_connections.copy()
        disconnected = set()
        
        for websocket in connections:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
                else:
                    disconnected.add(websocket)
            except Exception as e:
                logger.warning(f"广播消息失败: {e}")
                disconnected.add(websocket)
        
        # 清理断开的连接
        for ws in disconnected:
            self.disconnect(ws)
    
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