from __future__ import annotations

from fastapi import APIRouter

from app_models import ConnectionConfig, LogConfig


def create_config_router(
    *,
    get_connection_config_handler,
    update_connection_config_handler,
    get_log_config_handler,
    update_log_config_handler,
    save_log_entry_handler,
) -> APIRouter:
    router = APIRouter()

    @router.get('/api/config/connection')
    async def get_connection_config() -> dict:
        return await get_connection_config_handler()

    @router.post('/api/config/connection')
    async def update_connection_config(config_payload: ConnectionConfig) -> dict:
        return await update_connection_config_handler(config_payload)

    @router.get('/api/config/log')
    async def get_log_config() -> dict:
        return await get_log_config_handler()

    @router.post('/api/config/log')
    async def update_log_config(config_payload: LogConfig) -> dict:
        return await update_log_config_handler(config_payload)

    @router.post('/api/log/save')
    async def save_log_entry(data: dict) -> dict:
        return await save_log_entry_handler(data)

    return router