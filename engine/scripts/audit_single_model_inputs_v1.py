#!/usr/bin/env python3
"""Audit existing native observations before reusing them in either user track."""
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path

from mineru_vl_utils.post_process import json2md

ROOT = Path(__file__).resolve().parents[1]
MODEL = '/opt/p2t10/model'
WEIGHT_SHA = '01dcb5addfa1d6133fd0930e79fa2484817cb0228af21cb4917fa73d04fa3147'
NATIVES = {
    'initial': 'code/runtime/runs/native_full1651_gpu5_v2',
    'v21': 'runs/rsi_current_full_v21/base/native',
    'v21b': 'runs/rsi_current_full_v21b/base/native',
    'v25': 'runs/rsi_current_full_v25_supplemental/base/native',
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def audit(native, ids):
    receipt_path = native / 'predictions/worker_receipt.json'
    receipt = load(receipt_path)
    assert receipt['is_complete'] and receipt['status'] == 'complete'
    assert receipt['model'] == MODEL and receipt['model_weight_sha256'] == WEIGHT_SHA
    assert receipt['expected_count'] == receipt['processed_count'] == len(ids)
    assert receipt['single_checkpoint'] is True
    trace, http = native / 'predictions/route_trace.jsonl', native / 'audit/http.jsonl'
    routes = collections.Counter()
    response_hashes = collections.Counter()
    traced_responses = collections.Counter()
    for line in trace.open():
        item = json.loads(line)
        assert item['model'] == MODEL and item['endpoint_port'] == receipt['endpoint_port']
        assert item['page_id'] in ids and item['role'] == 'single_candidate'
        routes[item['native_type']] += 1
        if 'response_sha256' in item:
            traced_responses[item['response_sha256']] += 1
    assert dict(routes) == receipt['route_counts'] and routes['[layout]'] == len(ids)
    configured, consumed, tokens, stages = (collections.Counter() for _ in range(4))
    params = collections.Counter()
    finishes = collections.Counter()
    for line in http.open():
        item = json.loads(line)
        stages[item['stage']] += 1
        if item['stage'] == 'configured':
            assert item['parameters']['model'] == MODEL
            configured[item['request_sha256']] += 1
            params[json.dumps(item['parameters'], sort_keys=True)] += 1
        elif item['stage'] == 'consumed':
            response = item['response']
            assert response['model'] == MODEL
            consumed[item['request_sha256']] += 1
            for key in ['prompt_tokens', 'completion_tokens']:
                tokens[key] += response['usage'][key]
            for choice in response['choices']:
                finishes[str(choice['finish_reason'])] += 1
                content = choice['message'].get('content')
                if isinstance(content, str):
                    response_hashes[hashlib.sha256(content.encode()).hexdigest()] += 1
        else:
            raise AssertionError(('Unexpected native HTTP stage', item['stage']))
    assert configured == consumed
    assert sum(consumed.values()) == sum(routes.values())
    assert not (traced_responses - response_hashes), 'Trace responses absent from native server observations'
    rawdir, mddir = native / 'predictions/raw', native / 'predictions/markdown'
    assert {p.stem for p in rawdir.glob('*.json')} == {p.stem for p in mddir.glob('*.md')} == ids
    manifest = {}
    for page in sorted(ids):
        raw, md = rawdir / (page + '.json'), mddir / (page + '.md')
        assert json2md(load(raw)['blocks']) == md.read_text(), ('Native serialization changed', page)
        manifest[page] = {'raw': sha(raw), 'markdown': sha(md)}
    return dict(native=str(native.relative_to(ROOT)), pages=len(ids),
                receipt_sha256=sha(receipt_path), http_sha256=sha(http), trace_sha256=sha(trace),
                request_count=sum(consumed.values()), token_counts=dict(tokens),
                finish_reasons=dict(finishes), route_counts=dict(routes),
                sampling_parameter_groups=[dict(parameters=json.loads(k), requests=v) for k, v in params.items()],
                native_elapsed_seconds=receipt['elapsed_seconds'], predictions_sha256=manifest,
                pure_native_observations_verified=True,
                limits='Current outputs, trace and HTTP responses verified; this does not retrospectively invent an execution-time source freeze.')


def main():
    out = ROOT / 'reports/rsi_single_model_native_inputs_v1.json'
    assert not out.exists()
    pages = ROOT / 'code/runtime/runs/native_full1651_gpu5_v2/pages.json'
    ids = {r['id'] for r in load(pages)}
    assert len(ids) == 1651
    assert sha(Path(MODEL) / 'model.safetensors') == WEIGHT_SHA
    results = {name: audit(ROOT / relative, ids) for name, relative in NATIVES.items()}
    record = dict(at=dt.datetime.now(dt.timezone.utc).isoformat(), model=MODEL,
                  weights_sha256=WEIGHT_SHA, pages_sha256=sha(pages), runs=results,
                  current_worker_source_hashes={p: sha(ROOT / p) for p in [
                      'code/runtime/native_worker.py', 'code/runtime/audited_worker.py',
                      'code/runtime/run_native.py', 'code/runtime/http_audit.py']},
                  auxiliary_model_outputs_consumed=False)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({name: {k: r[k] for k in ['pages', 'request_count', 'native_elapsed_seconds',
                                               'pure_native_observations_verified']}
                      for name, r in results.items()}))


if __name__ == '__main__':
    main()
