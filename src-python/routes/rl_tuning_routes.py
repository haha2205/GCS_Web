from __future__ import annotations

from fastapi import APIRouter, Query

from app_models import (
    RLTuningApplyRequest,
    RLTuningEpisodeFinishRequest,
    RLTuningEpisodeStartRequest,
    RLTuningSessionControlRequest,
    RLTuningSessionRestoreRequest,
    RLTuningSessionStartRequest,
)


def create_rl_tuning_router(
    *,
    start_session_handler,
    stop_session_handler,
    pause_session_handler,
    resume_session_handler,
    restore_session_handler,
    start_episode_handler,
    finish_episode_handler,
    apply_params_handler,
    rollback_handler,
    get_status_handler,
    get_history_handler,
) -> APIRouter:
    router = APIRouter()

    @router.post('/api/rl-tuning/session/start')
    async def start_session(request: RLTuningSessionStartRequest) -> dict:
        return await start_session_handler(request)

    @router.post('/api/rl-tuning/session/stop')
    async def stop_session(request: RLTuningSessionControlRequest) -> dict:
        return await stop_session_handler(request)

    @router.post('/api/rl-tuning/session/pause')
    async def pause_session(request: RLTuningSessionControlRequest) -> dict:
        return await pause_session_handler(request)

    @router.post('/api/rl-tuning/session/resume')
    async def resume_session(request: RLTuningSessionControlRequest) -> dict:
        return await resume_session_handler(request)

    @router.post('/api/rl-tuning/session/restore')
    async def restore_session(request: RLTuningSessionRestoreRequest) -> dict:
        return await restore_session_handler(request)

    @router.post('/api/rl-tuning/episode/start')
    async def start_episode(request: RLTuningEpisodeStartRequest) -> dict:
        return await start_episode_handler(request)

    @router.post('/api/rl-tuning/episode/finish')
    async def finish_episode(request: RLTuningEpisodeFinishRequest) -> dict:
        return await finish_episode_handler(request)

    @router.post('/api/rl-tuning/apply')
    async def apply_params(request: RLTuningApplyRequest) -> dict:
        return await apply_params_handler(request)

    @router.post('/api/rl-tuning/rollback')
    async def rollback(request: RLTuningSessionControlRequest) -> dict:
        return await rollback_handler(request)

    @router.get('/api/rl-tuning/status')
    async def get_status() -> dict:
        return await get_status_handler()

    @router.get('/api/rl-tuning/history')
    async def get_history(session_id: str = Query(default='')) -> dict:
        return await get_history_handler(session_id)

    return router