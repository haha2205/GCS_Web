from typing import Any, Dict

from pydantic import BaseModel


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