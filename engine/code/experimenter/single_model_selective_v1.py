"""Track B: fresh cc1009 native -> budgeted E columns -> deterministic assembly.
Default is a non-executing plan. RSI admission must bind the exact plan SHA.
No prior predictions or auxiliary observation input is accepted.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlparse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
PYTHON = '/opt/p2t10/venv/bin/python'
MODEL = Path('/opt/p2t10/model')
WEIGHT_SHA = '01dcb5addfa1d6133fd0930e79fa2484817cb0228af21cb4917fa73d04fa3147'
HIDDEN = ['/opt/p2t10/hidden/OmniDocBench.json',
 '/opt/p2t10/hidden/source_validation_v2_references.jsonl',
 '/opt/p2t10/hidden/source_validation_v1_references.jsonl']
FILES = ['code/experimenter/single_model_selective_v1.py', 'code/runtime/run_native.py',
 'code/runtime/audited_worker.py', 'code/runtime/http_audit.py', 'code/runtime/e_current_v1.py',
 'code/experimenter/recognize_single_model_v1.py', 'code/runtime/native_content.py',
 'code/runtime/e_apply_current_v1.py', 'code/runtime/column_signature_v1.py',
 'scripts/apply_e_current.py', 'code/runtime/measure_processor.py',
 'code/runtime/score_frozen.py', 'code/runtime/score_receipts.py', 'scripts/compare_frozen_scores.py']


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def hidden(argv):
    script = 'set -euo pipefail\nn="$1"; shift\nfor ((i=0;i<n;i++)); do mount --bind /dev/null "$1"; test ! -s "$1"; shift; done\nexec "$@"'
    return ['unshare', '--mount', '--propagation', 'private', '/bin/bash', '-c', script,
            'single-model-no-gt', str(len(HIDDEN)), *HIDDEN, *map(str, argv)]


def dependencies():
    # Hash executable client implementation, not its separately trained models.
    import importlib.util
    package = Path(importlib.util.find_spec('mineru_vl_utils').origin).parent
    paths = [ROOT / p for p in FILES] + sorted(package.rglob('*.py'))
    paths += sorted(p for p in MODEL.iterdir() if p.suffix in ('.json', '.jinja', '.txt'))
    paths += [ROOT / 'agents/shared/runtime.json']
    for view in sorted((ROOT / 'code/runtime').glob('model-view-*')):
        paths += sorted(p for p in view.iterdir() if p.suffix in ('.json', '.jinja', '.txt'))
    return {str(p): sha(p) for p in paths}


def validate_pages(path):
    pages = load(path)
    assert pages and len({p['id'] for p in pages}) == len(pages)
    for p in pages:
        assert set(p) == {'id', 'image'}, 'Only image + artifact locator allowed'
        assert p['id'] and Path(p['id']).name == p['id'] and p['id'] not in ('.', '..')
        assert Path(p['image']).is_file()
    return pages


def admit(proposals, requests, maximum):
    """Keep whole column groups in input order; no page identity or GT decision."""
    chosen, kept, decisions = [], [], []
    for prop in proposals:
        cols = [r for r in requests if r['proposal'] == prop['proposal_id'] and r['kind'].startswith('col')]
        assert [r['kind'] for r in cols] == [f'col{i}' for i in range(len(prop['cuts']) - 1)]
        eligible = any(len(cols) % k == 0 for k in range(2, len(cols)))
        accepted = eligible and len(kept) + len(cols) <= maximum
        decisions.append({'proposal': prop['proposal_id'], 'accepted': accepted,
                          'reason': ('structurally_ineligible_signature' if not eligible else
                                     'within_request_budget' if accepted else 'budget_fallback'), 'requests': len(cols)})
        if accepted:
            chosen.append(prop)
            kept.extend(cols)
    return chosen, kept, decisions


def verify_native(native, pages_path):
    native = Path(native).resolve()
    report_path = ROOT/'reports/rsi_single_model_native_inputs_v1.json'
    report = load(report_path)
    assert report['model'] == str(MODEL) and report['weights_sha256'] == WEIGHT_SHA
    assert report['auxiliary_model_outputs_consumed'] == 0
    assert sha(pages_path) == report['pages_sha256'], 'Current diagnostic reuse requires exact audited full manifest'
    rows = [r for r in report['runs'].values() if (ROOT/r['native']).resolve() == native]
    assert len(rows) == 1 and rows[0]['pure_native_observations_verified'] is True
    row = rows[0]
    for relative,key in [('predictions/worker_receipt.json','receipt_sha256'),('audit/http.jsonl','http_sha256'),('predictions/route_trace.jsonl','trace_sha256')]:
        assert sha(native/relative) == row[key], relative
    for page in validate_pages(pages_path):
        for folder,ext in [('raw','.json'),('markdown','.md')]:
            assert sha(native/'predictions'/folder/(page['id']+ext)) == row['predictions_sha256'][page['id']][folder]
    return {'native':str(native),'RSI_audit':str(report_path),'RSI_audit_sha256':sha(report_path),
            'raw_md_pages_rehashed':len(row['predictions_sha256']), 'scope':'diagnostic reuse, not fresh cold'}


def internal(out, maximum):
    # Invoked only within the GT-hidden namespace, before any supplemental call.
    sys.path.insert(0, str(ROOT / 'code/runtime'))
    from e_current_v1 import prepare
    pages = load(out / 'pages.json')
    props, requests = prepare(out / 'native/predictions', pages, out / 'e')
    selected, kept, decisions = admit(props, requests, maximum)
    save(out / 'e/all_proposals.json', props)
    save(out / 'e/all_requests.json', requests)
    save(out / 'e/proposals.json', selected)
    save(out / 'e/requests.json', kept)
    save(out / 'e/budget_receipt.json', dict(configured=len(props), triggered=len(props),
         triggered_pages=len({p['page'] for p in props}), total_pages=len(pages),
         admitted_proposals=len(selected), logical_requests=len(kept), maximum_requests=maximum,
         unused_native_roi_requests_removed=sum(r['kind'] == 'native' for r in requests),
         decisions=decisions, selection_inputs='current native blocks and source pixels only'))


def provenance(out):
    native, candidate = out / 'native/predictions', out / 'e/applied/selected'
    dest = out / 'provenance'
    dest.mkdir()
    for p in load(out / 'pages.json'):
        pid = p['id']
        save(dest / (pid + '.json'), dict(source_image=p['image'], image_sha256=sha(p['image']),
             native_raw_sha256=sha(native / 'raw' / (pid + '.json')),
             native_markdown_sha256=sha(native / 'markdown' / (pid + '.md')),
             candidate_raw_sha256=sha(candidate / 'raw' / (pid + '.json')),
             candidate_markdown_sha256=sha(candidate / 'markdown' / (pid + '.md')),
             source=('RSI_audited_native_diagnostic_reuse' if (out/'native').is_symlink() else 'fresh_native_this_run'), auxiliary_inputs=[]))


def current_lease(gpu, expected):
    lease = load(ROOT / 'control/gpu_leases.json')[gpu]
    assert lease['state'] == 'READY' and lease['role'] == 'RSI'
    assert lease['endpoint'] == expected['endpoint'] and lease['container'] == expected['container']
    return lease


def run(plan, out, admission):
    permit = load(admission)
    assert permit['approved'] is True and permit['plan_sha256'] == sha(out / 'plan.json')
    assert permit['gpu'] == plan['gpu'] and permit['model'] == str(MODEL)
    assert dependencies() == plan['dependencies'], 'Code/config changed after plan'
    assert sha(MODEL / 'model.safetensors') == WEIGHT_SHA
    assert load(ROOT / 'agents/shared/runtime.json')['model'] == str(MODEL)
    assert sha(plan['pages']) == plan['pages_sha256']
    pages = validate_pages(plan['pages'])
    assert {p['image']: sha(p['image']) for p in pages} == plan['images']
    save(out / 'pages.json', pages)
    lease = current_lease(plan['gpu'], plan['lease'])
    port = urlparse(lease['endpoint']).port
    assert (ROOT/f'code/runtime/model-view-{port}/model.safetensors').resolve() == (MODEL/'model.safetensors').resolve()
    with urllib.request.urlopen(lease['endpoint']+'/v1/models', timeout=10) as response:
        served = json.load(response)
    assert {row['id'] for row in served['data']} == {str(MODEL)}, 'Unexpected served checkpoint'
    save(out/'served_model.json', served)
    state = dict(status='RUNNING', plan_sha256=sha(out / 'plan.json'), admission_sha256=sha(admission),
                 model=str(MODEL), weight_sha256=WEIGHT_SHA, steps=[], extra_calls=0, scored=False)
    save(out / 'pipeline.json', state)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='')
    def step(name, argv, gt_hidden=True):
        current_lease(plan['gpu'], plan['lease'])
        assert dependencies() == plan['dependencies']
        record = dict(name=name, argv=list(map(str, argv)), started=time.time(), gt_hidden=gt_hidden)
        state['steps'].append(record)
        save(out / 'pipeline.json', state)
        with (out / (name + '.log')).open('w') as log:
            rc = subprocess.run(hidden(argv) if gt_hidden else list(map(str, argv)),
                                env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
        record.update(returncode=rc, wall_seconds=time.time()-record['started'])
        save(out / 'pipeline.json', state)
        assert rc == 0, f'{name} failed: {rc}'
    def py(relative, *args):
        return [PYTHON, '-B', str(ROOT / relative), *map(str, args)]
    try:
        if plan['native_identity']:
            identity = verify_native(plan['native_identity']['native'], plan['pages'])
            assert identity == plan['native_identity']
            (out/'native').symlink_to(identity['native'], target_is_directory=True)
            state['native_reuse'] = identity
        else:
            step('native', py('code/runtime/run_native.py', '--pages', out/'pages.json', '--out', out/'native', '--port', port, '--audit'))
        receipt = load(out/'native/predictions/worker_receipt.json')
        assert receipt['status'] == 'complete' and receipt['processed_count'] == len(pages)
        assert receipt['model'] == str(MODEL) and receipt['model_weight_sha256'] == WEIGHT_SHA
        step('prepare_e', py('code/experimenter/single_model_selective_v1.py', '--internal', '--out', out,
                             '--max-extra-requests', plan['max_extra_requests']))
        requests = load(out/'e/requests.json')
        if requests:
            step('recognize_e', py('code/experimenter/recognize_single_model_v1.py', '--run', out/'e', '--port', port))
            assert len(load(out/'e/recognition.json')) == len(requests)
        else:
            save(out/'e/recognition.json', [])
        # Processor-only CPU replay inside the already running MinerU container.
        for name, audit in [('native', out/'native/audit')] + ([('e', out/'e/audit')] if requests else []):
            destination = out / (name + '_processor.json')
            step(name+'_processor', ['docker','exec','-e','CUDA_VISIBLE_DEVICES=','-e','OMP_NUM_THREADS=2',
                 lease['container'],'python3', ROOT/'code/runtime/measure_processor.py','--audit',audit,
                 '--model', ROOT/f'code/runtime/model-view-{port}', '--output', destination], False)
            assert load(destination)['all_prompt_counts_match'] is True
        step('apply_e', py('scripts/apply_e_current.py', '--e', out/'e'))
        provenance(out)
        records = load(out/'e/applied/receipt.json')
        usage = {'prompt_tokens': 0, 'completion_tokens': 0}
        rows = [json.loads(s) for s in (out/'e/audit/http.jsonl').read_text().splitlines()] if requests else []
        for row in rows:
            if row['stage'] == 'consumed':
                for key in usage:
                    usage[key] += row['response']['usage'][key]
        assert all(r['parameters']['model'] == str(MODEL) for r in rows if r['stage'] == 'configured')
        state.update(extra_calls=sum(r['stage']=='configured' for r in rows),
                     consumed=sum(r['stage']=='consumed' for r in rows), extra_tokens=usage,
                     selected=sum(r['accepted'] for r in records), fallback=sum(not r['accepted'] for r in records),
                     budget=load(out/'e/budget_receipt.json'), gpu_seconds=None,
                     gpu_seconds_note='Not measured; step wall time is not GPU utilization')
        if plan['score']:
            for name, pred in [('native',out/'native/predictions/markdown'),('candidate',out/'e/applied/selected/markdown')]:
                step('score_'+name, py('code/runtime/score_frozen.py','--predictions',pred,'--out',out/('score_'+name)),False)
            sys.path.insert(0,str(ROOT/'scripts'))
            from compare_frozen_scores import compare
            save(out/'paired.json',compare(out/'score_native/evaluation',out/'score_candidate/evaluation'))
            state['scored'] = True
        assert dependencies() == plan['dependencies']
        assert {p['image']: sha(p['image']) for p in pages} == plan['images']
        state['status'] = 'COMPLETE'
    except BaseException as error:
        state.update(status='FAILED', failure_class='RUN_OR_EVIDENCE_FAILURE', error=repr(error))
        raise
    finally:
        save(out/'pipeline.json',state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pages')
    parser.add_argument('--native-run',help='Diagnostic reuse of exact RSI-audited full native only')
    parser.add_argument('--out', required=True)
    parser.add_argument('--gpu', choices=['0','1','4','5'], default='5')
    parser.add_argument('--max-extra-requests', type=int, default=32)
    parser.add_argument('--score', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--admission')
    parser.add_argument('--internal', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    assert out.is_relative_to(ROOT / 'code/experimenter') and out != ROOT/'code/experimenter'
    assert 0 <= args.max_extra_requests <= 256
    if args.internal:
        assert all(not Path(p).read_bytes() for p in HIDDEN), 'GT not hidden'
        internal(out, args.max_extra_requests)
    elif args.execute:
        assert args.admission, 'Explicit RSI plan-bound admission required'
        assert not (out/'pipeline.json').exists(), 'No retry/overwrite of an existing run'
        try:
            run(load(out/'plan.json'),out,args.admission)
        except BaseException as error:
            save(out/'execution_failure.json', {'status':'FAILED','error':repr(error),
                 'failure_class':'RUN_OR_ADMISSION_FAILURE','prior_artifacts_retained':True})
            raise
    else:
        pages = validate_pages(args.pages)
        native_identity = verify_native(args.native_run,args.pages) if args.native_run else None
        out.mkdir(parents=True,exist_ok=False)
        plan = dict(schema='single_model_selective_v1', pages=str(Path(args.pages).resolve()),
             pages_sha256=sha(args.pages), images={p['image']:sha(p['image']) for p in pages},
             gpu=args.gpu,lease=load(ROOT/'control/gpu_leases.json')[args.gpu],
             model=str(MODEL),weight_sha256=WEIGHT_SHA,dependencies=dependencies(),
             max_extra_requests=args.max_extra_requests,score=args.score,
             stages=['fresh_native','pixel_e_prepare','bounded_same_model_columns','processor_replay','e_assemble'] +
                    (['official_native_score','official_candidate_score','paired'] if args.score else []),
             auxiliary_inputs=[], prior_prediction_inputs=([native_identity] if native_identity else []), native_identity=native_identity, runtime_GT=False,
             retries='native cc1009 defaults; supplemental cc1009 max_retries=3; no pipeline retry',
             budget_unit='logical requests; HTTP attempts including retries separately recorded')
        save(out/'plan.json',plan)
        print(json.dumps({'status':'PLAN_ONLY','plan':str(out/'plan.json'),'sha256':sha(out/'plan.json')}))


if __name__ == '__main__':
    main()
