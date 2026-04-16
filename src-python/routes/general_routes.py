from __future__ import annotations

from fastapi import APIRouter, WebSocket


def create_general_router(*, root_handler, health_handler, traffic_stats_handler, websocket_handler) -> APIRouter:
    router = APIRouter()

    @router.get('/')
    async def root() -> dict:
        return await root_handler()

    @router.get('/health')
    async def health_check() -> dict:
        return await health_handler()

    @router.get('/api/traffic/stats')
    async def get_traffic_stats() -> dict:
        return await traffic_stats_handler()

    @router.websocket('/ws/drone')
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket_handler(websocket)

    return router