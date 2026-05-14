from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ConnectionConfig(BaseModel):
    protocol: str = 'udp'
    listenAddress: str = '192.168.16.13'
    hostPort: int = 30509
    remoteIp: str = '192.168.16.116'
    commandRecvPort: int = 18504
    sendOnlyPort: int = 18506
    lidarSendPort: int = 18507
    planningSendPort: int = 18510
    planningRecvPort: int = 18511


class LogConfig(BaseModel):
    autoRecord: bool = False
    logFormat: str = 'csv'
    logLevel: str = '1'


class CommandRequest(BaseModel):
    type: str
    params: Dict[str, Any] = {}


class RecordingConfig(BaseModel):
    session_id: str = ''
    base_directory: str = ''
    case_id: str = ''


class RLTuningSessionStartRequest(BaseModel):
    session_id: str = ''
    task_type: str = 'velocity_tracking'
    parameter_keys: List[str] = Field(default_factory=lambda: ['fKeVx', 'fIeVx', 'fKeAx'])
    initial_params: Dict[str, Any] = Field(default_factory=dict)
    max_episodes: int = 20
    strategy_mode: str = 'torch_sac'


class RLTuningSessionControlRequest(BaseModel):
    session_id: str


class RLTuningSessionRestoreRequest(BaseModel):
    session_id: str = ''
    artifact_dir: str = ''


class RLTuningEpisodeStartRequest(BaseModel):
    session_id: str
    episode_id: str = ''


class RLTuningEpisodeFinishRequest(BaseModel):
    session_id: str
    episode_id: str = ''
    summary: Dict[str, Any] = Field(default_factory=dict)
    task_success: bool = True


class RLTuningApplyRequest(BaseModel):
    params: Dict[str, Any] = Field(default_factory=dict)