#!/usr/bin/env python3
"""Measure observed same-MinerU supplemental calls, without reading any GT."""
import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = '/opt/p2t10/model'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def measure(run, native=None):
    run = Path(run).resolve()
    native = Path(native).resolve() if native else None
    stages = []
    total_configured, total_consumed = collections.Counter(), collections.Counter()
    for path in sorted(run.rglob('http.jsonl')):
        if native and path.is_relative_to(native):
            continue
        configured, consumed, usage, finishes = (collections.Counter() for _ in range(4))
        times, tasks, failures = [], collections.Counter(), []
        for line in path.open():
            row = json.loads(line)
            if 'time' in row:
                times.append(row['time'])
            if row['stage'] == 'configured':
                assert row['parameters']['model'] == MODEL, path
                configured[row['request_sha256']] += 1
                tasks[json.dumps(row['prompts'], ensure_ascii=False, sort_keys=True)] += 1
            elif row['stage'] == 'consumed':
                response = row['response']
                assert response['model'] == MODEL, path
                consumed[row['request_sha256']] += 1
                for k in ['prompt_tokens', 'completion_tokens']:
                    usage[k] += response['usage'][k]
                for choice in response['choices']:
                    finishes[str(choice['finish_reason'])] += 1
            else:
                failures.append(row)
        assert configured == consumed, ('Incomplete supplemental observations', path)
        assert not failures, ('Failed supplemental HTTP requests', path)
        total_configured.update(configured)
        total_consumed.update(consumed)
        stages.append(dict(audit=str(path.relative_to(ROOT)), audit_sha256=sha(path),
                           requests=sum(configured.values()), tokens=dict(usage),
                           finish_reasons=dict(finishes),
                           observed_http_span_seconds=max(times)-min(times) if times else 0,
                           distinct_request_payloads=len(configured),
                           duplicate_payload_calls=sum(configured.values())-len(configured),
                           tasks=[dict(prompt=json.loads(k), calls=v) for k, v in tasks.items()]))
    result = dict(at=dt.datetime.now(dt.timezone.utc).isoformat(), run=str(run.relative_to(ROOT)),
                  model=MODEL, audit_logs=len(stages), stages=stages,
                  extra_requests=sum(total_configured.values()),
                  extra_tokens={k: sum(s['tokens'].get(k, 0) for s in stages)
                                for k in ['prompt_tokens', 'completion_tokens']},
                  distinct_request_payloads=len(total_configured),
                  duplicate_payload_calls=sum(total_configured.values())-len(total_configured),
                  observed_stage_http_span_sum_seconds=sum(s['observed_http_span_seconds'] for s in stages),
                  measured_GPU_seconds=None,
                  time_definition='HTTP observation spans include client/server/queue time; not GPU active time. Primary native excluded.',
                  auxiliary_models_observed=False)
    if native:
        receipt = load(native / 'predictions/worker_receipt.json')
        assert receipt['model'] == MODEL and receipt['is_complete']
        result.update(native=str(native.relative_to(ROOT)),
                      native_requests=sum(receipt['route_counts'].values()),
                      native_wall_seconds=receipt['elapsed_seconds'],
                      extra_requests_fraction_of_native=result['extra_requests']/sum(receipt['route_counts'].values()))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True)
    p.add_argument('--native', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    out = Path(a.out).resolve()
    assert out.is_relative_to(ROOT) and not out.exists()
    result = measure(a.run, a.native)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['run', 'extra_requests', 'extra_tokens',
                                            'duplicate_payload_calls', 'extra_requests_fraction_of_native']}))


if __name__ == '__main__':
    main()
