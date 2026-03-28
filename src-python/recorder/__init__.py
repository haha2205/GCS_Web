"""
数据录制器模块
支持按数据类型分文件存储，用于DSM离线分析
"""

from .data_recorder import RawDataRecorder, build_event_stream_paths, normalize_session_meta_for_thesis

__all__ = ['RawDataRecorder', 'build_event_stream_paths', 'normalize_session_meta_for_thesis']