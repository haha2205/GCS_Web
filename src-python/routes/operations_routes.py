from __future__ import annotations

from fastapi import APIRouter

from app_models import CommandRequest, RecordingConfig


def create_operations_router(
    *,
    start_udp_server_handler,
    stop_udp_server_handler,
    get_udp_status_handler,
    get_online_analysis_status_handler,
    send_command_handler,
    get_recording_status_handler,
    start_recording_handler,
    stop_recording_handler,
) -> APIRouter:
    router = APIRouter()

    @router.post('/api/udp/start')
    async def start_udp_server() -> dict:
        return await start_udp_server_handler()

    @router.post('/api/udp/stop')
    async def stop_udp_server() -> dict:
        return await stop_udp_server_handler()

    @router.get('/api/udp/status')
    async def get_udp_status() -> dict:
        return await get_udp_status_handler()

    @router.get('/api/online-analysis/status')
    async def get_online_analysis_status() -> dict:
        return await get_online_analysis_status_handler()

    @router.post('/api/command')
    async def send_command_to_drone(request: CommandRequest) -> dict:
        return await send_command_handler(request)

    @router.get('/api/recording/status')
    async def get_recording_status() -> dict:
        return await get_recording_status_handler()

    @router.post('/api/recording/start')
    async def start_recording(config_payload: RecordingConfig) -> dict:
        return await start_recording_handler(config_payload)

    @router.post('/api/recording/stop')
    async def stop_recording() -> dict:
        return await stop_recording_handler()

    return router