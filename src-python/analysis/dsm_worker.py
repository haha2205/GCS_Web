from __future__ import annotations

import json
import math
import os
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from config import MappingConfig
from export.session_standardizer import SessionStandardizer


@dataclass
class DsmRunResult:
    success: bool
    status: str
    session_dir: str
    output_path: str
    canonical_report_path: str
    summary: dict[str, Any]
    error: str = ''
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class SessionDsmWorker:
    def __init__(self, thesis_workspace: Optional[str | Path] = None, mapping_config: Optional[MappingConfig] = None):
        self.thesis_workspace = Path(
            thesis_workspace or os.getenv('THESIS_WS_PATH') or 'E:/DataAnalysis/thesis_ws'
        )
        self.mapping_config = mapping_config or MappingConfig()

    def run_for_session(self, session_dir: str | Path, start_time: Optional[float] = None, end_time: Optional[float] = None) -> DsmRunResult:
        session_path = Path(session_dir)
        analysis_dir = session_path / 'analysis'
        analysis_dir.mkdir(parents=True, exist_ok=True)
        canonical_report_path = analysis_dir / 'dsm_report.json'
        session_meta = self._load_session_meta(session_path)
        figure_context = self._extract_figure_context(session_meta)

        if not session_path.exists():
            return DsmRunResult(
                success=False,
                status='failed',
                session_dir=str(session_path),
                output_path='',
                canonical_report_path=str(canonical_report_path),
                summary={},
                error=f'会话目录不存在: {session_path}',
                start_time=start_time,
                end_time=end_time,
            )

        try:
            dsm_generator_cls = self._load_dsm_generator()
            generator = dsm_generator_cls(self.mapping_config)
            with tempfile.TemporaryDirectory(prefix=f'{session_path.name}_dsm_') as temp_root:
                input_dir = self._prepare_input_directory(session_path, Path(temp_root))
                result = generator.generate_dsm_report(
                    session_id=input_dir.name,
                    base_directory=str(input_dir.parent),
                    start_time=start_time,
                    end_time=end_time,
                    output_format='json',
                )
            sanitized_result = self._sanitize_for_json(result)
            meta = sanitized_result.setdefault('meta', {})
            meta['session_id'] = session_path.name
            meta.update(figure_context)
            with canonical_report_path.open('w', encoding='utf-8') as handle:
                json.dump(sanitized_result, handle, ensure_ascii=False, indent=2)

            return DsmRunResult(
                success=True,
                status='ready',
                session_dir=str(session_path),
                output_path=str(result.get('output_path', '')),
                canonical_report_path=str(canonical_report_path),
                summary=self._build_summary(sanitized_result, figure_context=figure_context),
                start_time=start_time,
                end_time=end_time,
            )
        except Exception as exc:
            return DsmRunResult(
                success=False,
                status='failed',
                session_dir=str(session_path),
                output_path='',
                canonical_report_path=str(canonical_report_path),
                summary={},
                error=str(exc),
                start_time=start_time,
                end_time=end_time,
            )

    def _prepare_input_directory(self, session_path: Path, temp_root: Path) -> Path:
        staged_session_dir = temp_root / session_path.name
        staged_session_dir.mkdir(parents=True, exist_ok=True)

        for file_name, source_path in self._collect_input_files(session_path).items():
            staged_path = staged_session_dir / file_name
            if source_path is None:
                self._write_empty_csv(staged_path, self._headers_for_file(file_name))
            else:
                shutil.copy2(source_path, staged_path)

        return staged_session_dir

    def _collect_input_files(self, session_path: Path) -> dict[str, Optional[Path]]:
        file_candidates = {
            'fcs_telemetry.csv': [
                session_path / 'records' / 'fcs' / 'fcs_telemetry.csv',
                session_path / 'fcs_telemetry.csv',
                session_path / 'analysis' / 'standardized' / 'fcs_telemetry.csv',
            ],
            'planning_telemetry.csv': [
                session_path / 'records' / 'planning' / 'planning_telemetry.csv',
                session_path / 'planning_telemetry.csv',
                session_path / 'analysis' / 'standardized' / 'planning_telemetry.csv',
            ],
            'radar_data.csv': [
                session_path / 'records' / 'lidar' / 'radar_data.csv',
                session_path / 'radar_data.csv',
                session_path / 'analysis' / 'standardized' / 'radar_data.csv',
            ],
            'bus_traffic.csv': [
                session_path / 'records' / 'bus' / 'bus_traffic.csv',
                session_path / 'bus_traffic.csv',
                session_path / 'analysis' / 'standardized' / 'bus_traffic.csv',
            ],
        }

        resolved: dict[str, Optional[Path]] = {}
        for file_name, candidates in file_candidates.items():
            source_path = next((candidate for candidate in candidates if candidate.exists()), None)
            resolved[file_name] = source_path

        return resolved

    def _headers_for_file(self, file_name: str) -> list[str]:
        for key, mapped_name in SessionStandardizer.STANDARD_FILES.items():
            if mapped_name == file_name:
                return list(SessionStandardizer.STANDARD_HEADERS[key])
        raise KeyError(f'unknown DSM input file: {file_name}')

    def _write_empty_csv(self, output_path: Path, headers: list[str]) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8', newline='') as handle:
            handle.write(','.join(headers) + '\n')

    def _load_dsm_generator(self):
        if not self.thesis_workspace.exists():
            raise FileNotFoundError(f'thesis_ws 不存在: {self.thesis_workspace}')

        thesis_path = str(self.thesis_workspace)
        if thesis_path not in sys.path:
            sys.path.insert(0, thesis_path)

        from data_processing.dsm import DSMGenerator  # type: ignore

        return DSMGenerator

    def _load_session_meta(self, session_path: Path) -> dict[str, Any]:
        meta_path = session_path / 'session_meta.json'
        if not meta_path.exists():
            return {}
        with meta_path.open('r', encoding='utf-8') as handle:
            return json.load(handle)

    def _extract_figure_context(self, session_meta: Optional[dict[str, Any]]) -> dict[str, Any]:
        meta = session_meta or {}
        figure_context: dict[str, Any] = {}
        for key in [
            'figure_run_id',
            'figure_batch_id',
            'figure_batch_group',
            'figure_ledger_range',
            'experiment_type',
            'chapter_target',
            'law_validation_scope',
            'analysis_run_id',
            'figure_asset_status',
            'figure_asset_ready',
            'figure_batch_manifest_path',
        ]:
            value = meta.get(key)
            if value is not None and value != '':
                figure_context[key] = value
        return figure_context

    def _build_summary(self, result: dict[str, Any], *, figure_context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        nodes = result.get('nodes', []) or []
        edges = result.get('edges', []) or []
        global_stats = result.get('global_stats', {}) or {}
        duration = (((result.get('meta') or {}).get('time_range') or {}).get('duration')) or 0

        total_bus_bytes = 0.0
        for edge in edges:
            profile = ((edge.get('attributes') or {}).get('profile') or {})
            avg_packet_size = float(profile.get('avg_packet_size') or 0)
            frequency_hz = float(profile.get('frequency_hz') or 0)
            total_bus_bytes += avg_packet_size * frequency_hz * float(duration or 0)

        cross_module_interactions = sum(
            1
            for edge in edges
            if edge.get('from') and edge.get('to') and edge.get('from') != edge.get('to')
        )

        return {
            'node_count': len(nodes),
            'edge_count': len(edges),
            'cross_module_interactions': cross_module_interactions,
            'total_bus_bytes': round(total_bus_bytes, 3),
            'avg_cross_latency': global_stats.get('cross_domain_latency_ms') or global_stats.get('avg_cross_latency') or 0,
            'global_stats_ready': bool(global_stats),
            **(figure_context or {}),
        }

    def _sanitize_for_json(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._sanitize_for_json(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._sanitize_for_json(item) for item in value]
        if hasattr(value, 'item') and callable(value.item):
            try:
                return self._sanitize_for_json(value.item())
            except Exception:
                pass
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return 0.0
        return value