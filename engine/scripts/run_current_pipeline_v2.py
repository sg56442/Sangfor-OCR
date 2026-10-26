#!/usr/bin/env python3
"""Execute the frozen current pipeline from fresh images or caller-native output.

All regional responses are generated anew. Service lifecycle is external and
RSI-owned. This executable is preparatory until its recorded run completes.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PYTHON = '/opt/p2t10/venv/bin/python'
HIDDEN_GT = ['/opt/p2t10/hidden/OmniDocBench.json',
             '/opt/p2t10/hidden/source_validation_v2_references.jsonl',
             '/opt/p2t10/hidden/source_validation_v1_references.jsonl']


def load(p):
    return json.loads(Path(p).read_text())


def save(p, value):
    p = Path(p)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(p)


def hidden(argv):
    script = 'set -euo pipefail\nn="$1"; shift\nfor ((i=0;i<n;i++)); do mount --bind /dev/null "$1"; test ! -s "$1"; shift; done\nexec "$@"'
    return ['unshare', '--mount', '--propagation', 'private', '/bin/bash', '-c', script,
            'ft1021-no-gt', str(len(HIDDEN_GT)), *HIDDEN_GT, *argv]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pages', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--gpu', choices=['0', '1', '4', '5'], required=True)
    p.add_argument('--native-run', help='Explicit existing run with predictions/ and audit/; no new native claim')
    p.add_argument('--table-columns', choices=['none', 'source', 'source+consolidation'], default='source+consolidation')
    p.add_argument('--no-score', action='store_true')
    p.add_argument('--freeze-name', help='Explicit RSI freeze snapshot filename under control/freezes')
    a = p.parse_args()
    out, pages = Path(a.out).resolve(), Path(a.pages).resolve()
    assert out.is_relative_to(ROOT)
    lease = load(ROOT / 'control/gpu_leases.json')[a.gpu]
    assert lease['role'] == 'RSI' and lease['state'] in ['READY', 'RSI_INTEGRATION'], 'RSI must first lease an idle owned endpoint'
    out.mkdir(parents=True, exist_ok=False)
    contract = load(ROOT / 'control/campaign_contract.json')
    deadline = datetime.datetime.fromisoformat(contract['deadline_at'])
    model = load(ROOT / 'agents/shared/runtime.json')['model']
    port = lease['endpoint'].rsplit(':', 1)[1]
    freeze_file = {'none': 'aecgeml_provisional_v1.json', 'source': 'aecgeqml_provisional_v1.json',
                   'source+consolidation': 'aecgeqnmlrv_provisional_v1.json'}[a.table_columns]
    if a.freeze_name:
        assert Path(a.freeze_name).name == a.freeze_name
        freeze_file = a.freeze_name
    freeze = load(ROOT / 'control/freezes' / freeze_file)
    hashes = dict(freeze['source_hashes'])
    for file in ['scripts/run_current_pipeline_v2.py', 'scripts/prepare_layout_current.py', 'scripts/apply_e_current.py',
                 'scripts/apply_representation_overlay_v2.py', 'scripts/probe_table_math_fonts.py',
                 'scripts/probe_formula_boundary_group.py', 'scripts/single_atom_vector_v1.py', 'scripts/compose_current_strategies_v2.py',
                 'code/research/typed_grid_source_guard.py']:
        hashes[file] = hashlib.sha256((ROOT / file).read_bytes()).hexdigest()
    if a.table_columns != 'none':
        for file in ['scripts/prepare_source_columns_current.py', 'scripts/compose_table_columns_current.py',
                     'scripts/recognize_ae_current.py']:
            hashes[file] = hashlib.sha256((ROOT / file).read_bytes()).hexdigest()
    state = dict(status='STARTING', steps=[], configured_pages=len(load(pages)),
                 native_generated_here=not bool(a.native_run), regional_candidates_fresh=True,
                 GPU=a.gpu, endpoint=lease['endpoint'], runtime_GT=False, source_hashes=hashes,
                 input_manifest_sha256=hashlib.sha256(pages.read_bytes()).hexdigest())
    state.update(table_columns=a.table_columns, freeze_file=freeze_file,
                 representation_rules=['fonts','aliases','formula-boundary','single-atom-vector'])

    def write():
        state['at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save(out / 'pipeline.json', state)

    def step(name, argv, gpu=False, conceal=True):
        assert datetime.datetime.now(datetime.timezone.utc) < deadline
        current = load(ROOT / 'control/gpu_leases.json')[a.gpu]
        if gpu:
            assert current['role'] == 'RSI' and current['endpoint'] == lease['endpoint']
        state['status'] = name.upper() + '_RUNNING'
        write()
        with (out / (name + '.log')).open('w') as log:
            result = subprocess.run(hidden(argv) if conceal else argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        state['steps'].append(dict(name=name, returncode=result.returncode, GPU=gpu))
        write()
        result.check_returncode()

    def py(script, *args):
        return [PYTHON, '-B', script, *map(str, args)]

    def processor(name, audit, dest):
        step(name, ['docker', 'exec', '-e', 'CUDA_VISIBLE_DEVICES=', '-e', 'OMP_NUM_THREADS=2',
                    lease['container'], 'python3', str(ROOT / 'code/runtime/measure_processor.py'),
                    '--audit', str(audit), '--model', str(ROOT / ('code/runtime/model-view-' + port)),
                    '--output', str(dest)], conceal=False)
        assert load(dest)['all_prompt_counts_match']

    def recognize(name, run):
        if load(run / 'requests.json'):
            step(name, py('code/runtime/recognize_manifest.py', '--run', run, '--port', port), gpu=True)
            processor(name + '_processor', run / 'audit', run / 'processor.json')
        else:
            save(run / 'recognition.json', [])

    write()
    try:
        for file, digest in hashes.items():
            assert hashlib.sha256((ROOT / file).read_bytes()).hexdigest() == digest, file
        if a.native_run:
            native = Path(a.native_run).resolve()
        else:
            native = out / 'native'
            step('native', py('code/runtime/run_native.py', '--pages', pages, '--out', native, '--port', port, '--audit'), gpu=True)
        native_receipt = load(native / 'predictions/worker_receipt.json')
        assert native_receipt['is_complete'] and native_receipt['processed_count'] == state['configured_pages']
        state['native_run'] = str(native)
        state['native_receipt_sha256'] = hashlib.sha256((native / 'predictions/worker_receipt.json').read_bytes()).hexdigest()
        prediction = native / 'predictions'
        step('ae_build', py('code/research/build_ae_runtime.py', '--pages', pages, '--native', prediction,
                           '--http', native / 'audit', '--endpoint', lease['endpoint'], '--model', model, '--out', out / 'ae'))
        step('ae_recognize', py('scripts/recognize_ae_current.py', '--requests', out / 'ae/requests.json',
                               '--out', out / 'ae_answers', '--endpoint', lease['endpoint'], '--model', model), gpu=True)
        step('g_prepare', py('code/runtime/prepare_g_current_run.py', '--native', prediction, '--pages', pages,
                            '--native-audit', native / 'audit', '--out', out / 'g'))
        probe = out / 'g/probe'
        triggered = {i for i, prop in enumerate(load(probe / 'proposals.json')) if prop['triggered']}
        all_requests = load(probe / 'requests.json')
        admitted = [q for q in all_requests if q['proposal'] in triggered]
        save(probe / 'requests.json', admitted)
        save(probe / 'admission_receipt.json', dict(configured=len(all_requests), triggered=len(admitted),
                                                   diagnostic_requests_omitted=len(all_requests)-len(admitted), runtime_GT=False))
        recognize('g_recognize', probe)
        from g_boundary_current import prepare as boundary_prepare
        boundary = out / 'g/boundary'
        boundary_prepare(probe, boundary)
        recognize('g_boundary_recognize', boundary)
        original, new = load(probe / 'recognition.json'), load(boundary / 'recognition.json')
        replacement = {(q['proposal'], q['kind']): q for q in new}
        save(boundary / 'merged_recognition.json', [replacement.get((q['proposal'], q['kind']), q) for q in original])
        step('aecg_compose', py('scripts/compose_current_strategies_v2.py', '--native', prediction, '--pages', pages,
                               '--ae', out / 'ae', '--ae-answers', out / 'ae_answers/answers.json', '--g', out / 'g', '--out', out / 'aecg'))
        step('e_prepare', py('code/runtime/e_current_v1.py', '--native', prediction, '--pages', pages, '--out', out / 'e'))
        recognize('e_recognize', out / 'e')
        step('e_apply', py('scripts/apply_e_current.py', '--e', out / 'e'))
        step('e_compose', py('scripts/compose_e_overlay.py', '--native', prediction, '--combined', out / 'aecg', '--e', out / 'e', '--out', out / 'aecge'))
        pre_math = out / 'aecge'
        if a.table_columns != 'none':
            step('columns_prepare', py('scripts/prepare_source_columns_current.py', '--native', prediction,
                                       '--pages', pages, '--out', out / 'columns'))
            step('columns_recognize', py('scripts/recognize_ae_current.py', '--requests', out / 'columns/requests.json',
                                         '--out', out / 'column_answers', '--endpoint', lease['endpoint'], '--model', model), gpu=True)
            if load(out / 'columns/requests.json'):
                processor('columns_processor', out / 'column_answers/http_audit', out / 'columns/processor.json')
            extra = ['--consolidation'] if a.table_columns == 'source+consolidation' else []
            step('columns_compose', py('scripts/compose_table_columns_current.py', '--native', prediction,
                                       '--pages', pages, '--combined', pre_math, '--columns', out / 'columns',
                                       '--answers', out / 'column_answers', '--out', out / 'aecgeq', *extra))
            pre_math = out / 'aecgeq'
        step('m_compose', py('scripts/apply_table_math_overlay.py', '--combined', pre_math, '--out', out / 'aecgem'))
        step('layout_prepare', py('scripts/prepare_layout_current.py', '--native', prediction, '--pages', pages,
                                 '--e', out / 'e', '--out', out / 'layout'))
        group, dense = out / 'layout/group', out / 'layout/dense'
        if load(group / 'requests.json'):
            step('group_recognize', py('code/runtime/recognize_layout_0010.py', '--run', group, '--port', port), gpu=True)
            processor('group_processor', group / 'audit', group / 'processor.json')
        else:
            save(group / 'recognition.json', [])
        if load(dense / 'tiles.json'):
            step('rowpair_recognize', py('code/runtime/run_native.py', '--pages', dense / 'tiles.json',
                                       '--out', dense / 'inference', '--port', port, '--audit'), gpu=True)
            processor('rowpair_processor', dense / 'inference/audit', dense / 'processor.json')
        step('layout_compose', py('scripts/compose_layout_overlay.py', '--native', prediction, '--combined', out / 'aecgem',
                                 '--group', group, '--dense', dense, '--out', out / 'layout_combined'))
        step('representation_compose', py('scripts/apply_representation_overlay_v2.py',
              '--combined', out / 'layout_combined', '--out', out / 'combined', '--features',
              'fonts', 'aliases', 'formula-boundary', 'single-atom-vector'))
        for file, digest in hashes.items():
            assert hashlib.sha256((ROOT / file).read_bytes()).hexdigest() == digest, file
        state['inference_complete'] = True
        write()
        if not a.no_score:
            step('score', py('code/runtime/score_frozen.py', '--predictions', out / 'combined/predictions/markdown',
                            '--out', out / 'score'), conceal=False)
        state['status'] = 'COMPLETE'
        write()
    except BaseException as error:
        state.update(status='FAILED', error=repr(error))
        write()
        raise


if __name__ == '__main__':
    main()
