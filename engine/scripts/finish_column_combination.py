#!/usr/bin/env python3
"""Finish M/L overlays and official full score after source-column composition."""
import datetime
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/rsi_aecgeqml_first'
PYTHON = '/opt/p2t10/venv/bin/python'


def main():
    assert json.loads((OUT / 'column_combined/composition_receipt.json').read_text())['status'] == 'COMPLETE'
    state = dict(status='STARTING', scope='Same-current-native frozen response combination; no independent repeat', steps=[])
    jobs = [
        ('math', [PYTHON, '-B', 'scripts/apply_table_math_overlay.py', '--combined', str(OUT / 'column_combined'), '--out', str(OUT / 'math_combined')]),
        ('layout', [PYTHON, '-B', 'scripts/compose_layout_overlay.py', '--native', 'code/runtime/runs/native_full1651_gpu5_v2/predictions',
                    '--combined', str(OUT / 'math_combined'), '--group', 'code/experimenter/runs/local_layout_group_0011',
                    '--dense', 'code/experimenter/runs/local_layout_dense_0011', '--out', str(OUT / 'combined')]),
        ('score', [PYTHON, '-B', 'code/runtime/score_frozen.py', '--predictions', str(OUT / 'combined/predictions/markdown'),
                   '--out', str(OUT / 'score'), '--cache', 'runs/rsi_aecgem_first/score/cdm_cache']),
    ]
    def write():
        state['at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        (OUT / 'pipeline.json').write_text(json.dumps(state, indent=2) + '\n')
    try:
        for name, argv in jobs:
            state['status'] = name.upper() + '_RUNNING'
            write()
            with (OUT / (name + '.log')).open('w') as log:
                result = subprocess.run(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            state['steps'].append(dict(name=name, returncode=result.returncode))
            result.check_returncode()
        state['status'] = 'COMPLETE'
    except BaseException as error:
        state.update(status='FAILED', error=repr(error))
        raise
    finally:
        write()


if __name__ == '__main__':
    main()
