from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.dsm_worker import SessionDsmWorker
from config import MappingConfig
from export.session_standardizer import SessionStandardizer


def main() -> int:
    if len(sys.argv) < 2:
        print('usage: validate_session_pipeline.py <session_dir>')
        return 1

    session_dir = Path(sys.argv[1]).resolve()
    source_analysis_dir = session_dir / 'analysis'
    source_analysis_dir.mkdir(parents=True, exist_ok=True)
    source_output_path = source_analysis_dir / 'validation_summary.json'

    with tempfile.TemporaryDirectory(prefix=f'{session_dir.name}_', dir=str(session_dir.parent)) as temp_root:
        temp_session_dir = Path(temp_root) / session_dir.name
        shutil.copytree(session_dir, temp_session_dir)

        analysis_dir = temp_session_dir / 'analysis'
        analysis_dir.mkdir(parents=True, exist_ok=True)
        output_path = analysis_dir / 'validation_summary.json'

        result = SessionStandardizer(temp_session_dir).export()
        payload = {
            'source_session_dir': str(session_dir),
            'validated_session_dir': str(temp_session_dir),
            'file_status': result.file_status,
            'required_files': result.required_files,
            'optional_files': result.optional_files,
            'configured_input_weights': result.configured_input_weights,
            'effective_input_weights': result.effective_input_weights,
            'notes': result.notes,
        }

        has_real_inputs = any(result.file_status.get(key) == 'ready' for key in [*result.required_files, *result.optional_files])
        if has_real_inputs:
            dsm_result = SessionDsmWorker(mapping_config=MappingConfig()).run_for_session(temp_session_dir).as_dict()
            payload['dsm_status'] = dsm_result.get('status')
            payload['dsm_error'] = dsm_result.get('error', '')
            payload['dsm_summary'] = dsm_result.get('summary', {})
            payload['dsm_report_path'] = dsm_result.get('canonical_report_path', '')
        else:
            payload['dsm_status'] = 'blocked'
            payload['dsm_error'] = 'no real inputs ready'
            payload['dsm_summary'] = {}
            payload['dsm_report_path'] = ''

        summary_text = json.dumps(payload, ensure_ascii=False, indent=2)
        output_path.write_text(summary_text, encoding='utf-8')
        source_output_path.write_text(summary_text, encoding='utf-8')
        print(source_output_path)
        return 0

if __name__ == '__main__':
    raise SystemExit(main())