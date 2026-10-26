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
import os
import shutil
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_model_selective_v1 import MODEL, WEIGHT_SHA, sha, dependencies
from single_model_native_runtime_v1 import verify_native

ROOT = Path(__file__).resolve().parents[2]
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
    p.add_argument('--gpu', choices=['0', '1', '3'], required=True)
    p.add_argument('--native-run', required=True, help='Explicit existing run with predictions/ and audit/; no new native claim')
    p.add_argument('--table-columns', choices=['source+consolidation'], default='source+consolidation')
    p.add_argument('--no-score', action='store_true')
    p.add_argument('--freeze-name', help='Explicit RSI freeze snapshot filename under control/freezes')
    p.add_argument('--execute',action='store_true')
    p.add_argument('--admission',required=True)
    p.add_argument('--final-validation-admission')
    p.add_argument('--final-validation-sha256')
    p.add_argument('--check-time-only',action='store_true')
    p.add_argument('--max-extra-requests',type=int,default=1200)
    p.add_argument('--max-dense-tiles',type=int,default=64)
    a = p.parse_args()
    assert a.execute and a.no_score, 'RSI runs prepared entry; scoring is separate'
    from phase2_final_time_gate_v1 import deadline as resolve_deadline
    time_binding=dict(kind='B_core',input_admission_sha256=sha(a.admission),out=str(Path(a.out).resolve()),gpu=a.gpu,budget=a.max_extra_requests,max_dense_tiles=a.max_dense_tiles,native_run=str(Path(a.native_run).resolve()),pages_sha256=sha(a.pages))
    deadline=resolve_deadline(ROOT,__file__,time_binding,a.final_validation_admission,a.final_validation_sha256)
    if a.check_time_only:
        print(json.dumps(dict(status='TIME_ADMISSION_PASS',deadline=deadline.isoformat(),model_calls=0)));return
    from phase2_runtime_guard_v1 import guard
    binding=guard(a.gpu)
    assert 0 <= a.max_extra_requests <= 2048 and 0 <= a.max_dense_tiles <= 64
    permit=load(a.admission)
    assert permit['approved'] is True
    assert permit['entry_sha256']==sha(__file__)
    efficient_files=['phase2_b_prime_v4.py','phase2_final_time_gate_v1.py','phase2_runtime_guard_v1.py','phase2_prime_stage_v1.py','compose_table_columns_prime_v4.py','strict_math_prime_v4.py','source_column_prime_api_v4.py','source_column_prime_guard_v4.py','g_selective_no_rerun_v1.py','g_boundary_no_rerun_v1.py','compose_single_model_efficient_v1.py','single_model_native_runtime_v1.py','http_budget_v1.py','http_budget_bootstrap/sitecustomize.py','single_model_stage_rates_v1.py']
    assert permit['native_auditor_sha256']==sha(ROOT/'scripts/audit_single_model_inputs_v1.py')
    assert permit['cost_tool_sha256']==sha(ROOT/'scripts/summarize_single_model_cost_v1.py')
    column_gate_files=['scripts/source_column_request_gate_v1.py','scripts/prepare_source_columns_selective_v1.py','scripts/compose_table_columns_selective_v1.py']
    assert permit['column_gate_hashes']=={f:sha(ROOT/f) for f in column_gate_files}
    assert permit['efficiency_source_hashes']=={f:sha(ROOT/'code/experimenter'/f) for f in efficient_files}
    assert permit['pages_sha256']==sha(a.pages) and permit['gpu']==a.gpu
    assert permit['table_columns']==a.table_columns
    assert permit['max_extra_requests']==a.max_extra_requests and permit['max_dense_tiles']==a.max_dense_tiles
    assert permit['score']==(not a.no_score)
    assert permit['native_run']==(str(Path(a.native_run).resolve()) if a.native_run else None)
    assert binding['model']==str(MODEL) and binding['weight_sha256']==WEIGHT_SHA
    native_identity=verify_native(a.native_run,a.pages) if a.native_run else None
    dependency_snapshot=dependencies()
    assert permit['dependency_snapshot']==dependency_snapshot
    out, pages = Path(a.out).resolve(), Path(a.pages).resolve()
    assert out.is_relative_to(ROOT/'code/experimenter')
    lease = load(ROOT / 'control/gpu_leases.json')[a.gpu]
    assert lease['role'] == 'RSI' and lease['state'] in ['READY', 'RSI_INTEGRATION'], 'RSI must first lease an idle owned endpoint'
    out.mkdir(parents=True, exist_ok=False)
    save(out/'http_budget.json',dict(maximum=a.max_extra_requests,reserved=0,denied=0,exhausted=False))
    contract = load(ROOT / 'control/campaign_contract.json')
    # deadline resolved before any service access: diagnostics drain or explicit final permit
    model = load(ROOT / 'agents/shared/runtime.json')['model']
    assert model==str(MODEL)
    port = lease['endpoint'].rsplit(':', 1)[1]
    freeze_file = {'none': 'aecgeml_provisional_v1.json', 'source': 'aecgeqml_provisional_v1.json',
                   'source+consolidation': 'aecgeqnmlrv_provisional_v1.json'}[a.table_columns]
    if a.freeze_name:
        assert Path(a.freeze_name).name == a.freeze_name
        freeze_file = a.freeze_name
    freeze = load(ROOT / 'control/freezes' / freeze_file)
    assert permit['freeze_sha256']==sha(ROOT/'control/freezes'/freeze_file)
    hashes = dict(freeze['source_hashes'])
    rules=ROOT/'reports/researcher_0006p/rules_freeze_v4.json'
    extra_hashes=dict(load(rules)['source_hashes'])
    extra_hashes[str(rules)]=sha(rules)
    extra_hashes[str(ROOT/'code/research/run_native_rules_track_a_v1.py')]=sha(ROOT/'code/research/run_native_rules_track_a_v1.py')
    assert permit['phase2_source_hashes']==extra_hashes
    hashes.update(extra_hashes)
    hashes.update(permit['column_gate_hashes'])
    hashes['scripts/audit_single_model_inputs_v1.py']=permit['native_auditor_sha256']
    hashes['scripts/summarize_single_model_cost_v1.py']=permit['cost_tool_sha256']
    hashes['code/experimenter/phase2_b_prime_v4.py']=sha(__file__)
    for f in efficient_files: hashes['code/experimenter/'+f]=sha(ROOT/'code/experimenter'/f)
    for file in ['g_selective_no_rerun_v1.py','g_boundary_no_rerun_v1.py','compose_single_model_efficient_v1.py','single_model_native_runtime_v1.py','http_budget_v1.py','http_budget_bootstrap/sitecustomize.py','single_model_stage_rates_v1.py']:
        hashes['code/experimenter/'+file]=sha(ROOT/'code/experimenter'/file)
    hashes['code/experimenter/single_model_selective_v1.py']=sha(ROOT/'code/experimenter/single_model_selective_v1.py')
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
    state.update(admission_sha256=sha(a.admission), native_identity=native_identity, supplemental_requests_admitted=0, dense_tiles_admitted=0, dependency_snapshot=dependency_snapshot)
    state.update(table_columns=a.table_columns, freeze_file=freeze_file,
                 representation_rules=['fonts','aliases','formula-boundary','single-atom-vector'])

    def write():
        state['at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save(out / 'pipeline.json', state)

    def step(name, argv, gpu=False, conceal=True):
        assert datetime.datetime.now(datetime.timezone.utc) < deadline
        current = load(ROOT / 'control/gpu_leases.json')[a.gpu]
        if gpu:
            assert current['role'] == 'RSI' and current['state']=='READY' and current['endpoint'] == lease['endpoint'] and current['service_running'] and current['available_for_inference'] and current['container_id']==binding['container_id']
            assert dependencies()==dependency_snapshot
            if name != 'native':
                if '--requests' in argv:
                    count=len(load(argv[argv.index('--requests')+1]))
                elif '--run' in argv:
                    count=len(load(Path(argv[argv.index('--run')+1])/'requests.json'))
                elif name=='rowpair_recognize':
                    count=0
                    tiles=len(load(argv[argv.index('--pages')+1]))
                    assert tiles<=a.max_dense_tiles, 'DENSE_TILE_BUDGET_EXCEEDED'
                    state['dense_tiles_admitted']+=tiles
                else:
                    raise AssertionError('Unknown GPU stage: '+name)
                assert state['supplemental_requests_admitted']+count<=a.max_extra_requests, 'REQUEST_BUDGET_EXCEEDED'
                state['supplemental_requests_admitted']+=count
        state['status'] = name.upper() + '_RUNNING'
        write()
        env=dict(os.environ)
        if gpu and name!='native':
            env['FT1021_SUPPLEMENTAL_BUDGET']=str(out/'http_budget.json')
            env['PYTHONPATH']=str(ROOT/'code/experimenter/http_budget_bootstrap')+os.pathsep+env.get('PYTHONPATH','')
        else:
            env.pop('FT1021_SUPPLEMENTAL_BUDGET',None)
        started=time.time()
        with (out / (name + '.log')).open('w') as log:
            result = subprocess.run(hidden(argv) if conceal else argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,env=env)
        state['steps'].append(dict(name=name, returncode=result.returncode, GPU=gpu, wall_seconds=time.time()-started, argv=argv))
        write()
        result.check_returncode()

    def py(script, *args):
        return [PYTHON, '-B', script, *map(str, args)]

    def processor(name, audit, dest):
        step(name, ['docker', 'exec', '-e', 'CUDA_VISIBLE_DEVICES=', '-e', 'OMP_NUM_THREADS=2',
                    lease['container'], 'python3', str(ROOT / 'code/runtime/measure_processor.py'),
                    '--audit', str(audit), '--model', binding['processor_model_view'],
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
        save(probe / 'geometry_requests.json', all_requests)
        admitted = [q for q in all_requests if q['proposal'] in triggered and q['kind']!='native']
        save(probe / 'requests.json', admitted)
        save(probe / 'admission_receipt.json', dict(configured=len(all_requests), triggered=len(admitted),
                                                   diagnostic_requests_omitted=sum(q['proposal'] not in triggered for q in all_requests),
                                                   native_reruns_omitted=sum(q['proposal'] in triggered and q['kind']=='native' for q in all_requests),runtime_GT=False))
        recognize('g_recognize', probe)
        from g_boundary_no_rerun_v1 import prepare as boundary_prepare
        boundary = out / 'g/boundary'
        boundary_prepare(probe, boundary)
        recognize('g_boundary_recognize', boundary)
        original, new = load(probe / 'recognition.json'), load(boundary / 'recognition.json')
        replacement = {(q['proposal'], q['kind']): q for q in new}
        save(boundary / 'merged_recognition.json', [replacement.get((q['proposal'], q['kind']), q) for q in original])
        step('aecg_compose', py('code/experimenter/compose_single_model_efficient_v1.py', '--native', prediction, '--pages', pages,
                               '--ae', out / 'ae', '--ae-answers', out / 'ae_answers/answers.json', '--g', out / 'g', '--out', out / 'aecg'))
        step('e_prepare', py('code/runtime/e_current_v1.py', '--native', prediction, '--pages', pages, '--out', out / 'e'))
        # The E selector never reads the redundant whole-block ROI answer.
        e_requests=load(out/'e/requests.json')
        save(out/'e/all_requests_before_efficiency.json',e_requests)
        save(out/'e/requests.json',[q for q in e_requests if q['kind']!='native'])
        recognize('e_recognize', out / 'e')
        step('e_apply', py('scripts/apply_e_current.py', '--e', out / 'e'))
        step('e_compose', py('scripts/compose_e_overlay.py', '--native', prediction, '--combined', out / 'aecg', '--e', out / 'e', '--out', out / 'aecge'))
        pre_math = out / 'aecge'
        if a.table_columns != 'none':
            step('columns_prepare', py('scripts/prepare_source_columns_selective_v1.py', '--native', prediction,
                                       '--pages', pages, '--out', out / 'columns'))
            step('columns_recognize', py('scripts/recognize_ae_current.py', '--requests', out / 'columns/requests.json',
                                         '--out', out / 'column_answers', '--endpoint', lease['endpoint'], '--model', model), gpu=True)
            if load(out / 'columns/requests.json'):
                processor('columns_processor', out / 'column_answers/http_audit', out / 'columns/processor.json')
            extra = ['--consolidation'] if a.table_columns == 'source+consolidation' else []
            from phase2_prime_stage_v1 import column_command
            step('columns_compose', column_command(prediction,pages,pre_math,out/'columns',out/'column_answers',out/'aecgeq'))
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
        state['http_budget']=load(out/'http_budget.json')
        assert state['http_budget']['reserved']<=a.max_extra_requests
        from summarize_single_model_cost_v1 import measure as cost_measure
        from single_model_stage_rates_v1 import measure as rates_measure
        save(out/'actual_costs.json',cost_measure(out,native))
        save(out/'stage_rates.json',rates_measure(out))
        state['inference_complete'] = True
        write()
        if not a.no_score:
            step('score', py('code/runtime/score_frozen.py', '--predictions', out / 'combined/predictions/markdown',
                            '--out', out / 'score'), conceal=False)
        # Aggregate actual wire attempts/tokens separately from admission estimates.
        wire=[]
        for audit in out.rglob('http.jsonl'):
            if not audit.is_relative_to(out/'native'):
                wire += [json.loads(line) for line in audit.read_text().splitlines()]
        state['supplemental_wire']={'configured':sum(r['stage']=='configured' for r in wire),
            'consumed':sum(r['stage']=='consumed' for r in wire),
            'failed_response':sum(r['stage']=='failed_response' for r in wire),
            'tokens':{k:sum(r['response']['usage'][k] for r in wire if r['stage']=='consumed') for k in ['prompt_tokens','completion_tokens']},
            'GPU_seconds':None,'gain_vs_track_A':None}
        if not a.no_score:
            step('native_score',py('code/runtime/score_frozen.py','--predictions',prediction/'markdown','--out',out/'native_score'),conceal=False)
            from compare_frozen_scores import compare
            save(out/'paired.json',compare(out/'native_score/evaluation',out/'score/evaluation'))
        assert dependencies()==dependency_snapshot
        if native_identity: assert verify_native(a.native_run,a.pages)==native_identity
        state['status'] = 'COMPLETE'
        write()
    except BaseException as error:
        state.update(status='FAILED', error=repr(error), failure_class='RUN_OR_BUDGET_OR_EVIDENCE_FAILURE')
        budget=load(out/'http_budget.json');state['http_budget']=budget
        if budget['exhausted'] or 'BUDGET_EXCEEDED' in str(error):
            fallback=out/'native_budget_fallback'
            shutil.copytree(native/'predictions/raw',fallback/'predictions/raw')
            shutil.copytree(native/'predictions/markdown',fallback/'predictions/markdown')
            save(fallback/'receipt.json',dict(status='NATIVE_FALLBACK',reason='supplemental_budget',native=str(native),native_identity=verify_native(native,pages),model_calls=0))
            state.update(status='BUDGET_FALLBACK_RSI_REVIEW',fallback=str(fallback),inference_complete=False)
        write()
        raise


if __name__ == '__main__':
    main()
