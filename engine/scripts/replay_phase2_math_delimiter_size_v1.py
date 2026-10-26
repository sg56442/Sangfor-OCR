#!/usr/bin/env python3
"""Replay the fixed paired-visible-math sizing rule on arbitrary campaign inputs."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
GT = [
    '/opt/p2t10/hidden/OmniDocBench.json',
    '/opt/p2t10/hidden/source_validation_v2_references.jsonl',
    '/opt/p2t10/hidden/source_validation_v1_references.jsonl',
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--hidden', action='store_true')
    args = parser.parse_args()
    if not args.hidden:
        hidden = [p for p in GT if Path(p).exists()]
        shell = ('set -euo pipefail\nn="$1"; shift\n'
                 'for ((i=0;i<n;i++)); do mount --bind /dev/null "$1"; '
                 'test ! -s "$1"; shift; done\nexec "$@"')
        subprocess.run([
            'unshare', '--net', '--mount', '--propagation', 'private', '/bin/bash',
            '-c', shell, 'phase2-math-sizing', str(len(hidden)), *hidden,
            sys.executable, '-B', str(Path(__file__).resolve()),
            *sys.argv[1:], '--hidden',
        ], check=True, cwd=ROOT, env=dict(os.environ, CUDA_VISIBLE_DEVICES='',
             OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1'))
        return
    assert all(not Path(p).exists() or Path(p).stat().st_size == 0 for p in GT)
    sys.path.insert(0, str(ROOT / 'code/research'))
    from phase2_math_delimiter_size_v1 import transform
    source, out = Path(args.predictions).resolve(), Path(args.out).resolve()
    assert source.is_relative_to(ROOT) and out.is_relative_to(ROOT) and not out.exists()
    raw_paths = sorted((source / 'raw').glob('*.json'))
    assert raw_paths
    assert {p.stem for p in raw_paths} == {p.stem for p in (source / 'markdown').glob('*.md')}
    for sub in ['raw', 'markdown']:
        (out / 'predictions' / sub).mkdir(parents=True)
    records, scans = [], []
    start, tables = time.monotonic(), 0
    for rp in raw_paths:
        mp = source / 'markdown' / (rp.stem + '.md')
        original = json.loads(rp.read_text())
        raw, markdown = copy.deepcopy(original), mp.read_text()
        changes = []
        for index, block in enumerate(raw['blocks']):
            if block.get('type') != 'table':
                continue
            tables += 1
            before = block.get('content')
            if not isinstance(before, str):
                continue
            parts, traces = re.split(r'(<[^>]+>)', before), []
            for segment_index, segment in enumerate(parts):
                if segment.startswith('<'):
                    continue
                rewritten, spans = transform(segment)
                assert transform(rewritten)[0] == rewritten
                for span in spans:
                    # The rule only removes literal sizing commands; retain every glyph.
                    assert re.sub(r'\\(?:left|right)\b', '', span['before']) == span['after']
                parts[segment_index] = rewritten
                traces.extend(dict(segment_index=segment_index, **span) for span in spans)
            after = ''.join(parts)
            if after == before:
                continue
            unique = markdown.count(before) == 1
            scans.append(dict(page_evidence_only=rp.stem, index=index,
                              applied=unique, reason='unique_markdown_owner' if unique
                              else 'ambiguous_markdown_owner', spans=len(traces)))
            if not unique:
                continue
            markdown = markdown.replace(before, after, 1)
            block['content'] = after
            changes.append(dict(index=index, before=before, after=after, traces=traces))
        restored = copy.deepcopy(raw)
        for change in changes:
            restored['blocks'][change['index']]['content'] = change['before']
        assert restored == original
        ro, mo = out / 'predictions/raw' / rp.name, out / 'predictions/markdown' / mp.name
        if changes:
            ro.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n')
            mo.write_text(markdown)
        else:
            os.link(rp, ro)
            os.link(mp, mo)
        records.append(dict(page_evidence_only=rp.stem,
            input_raw_sha256=sha(rp), input_markdown_sha256=sha(mp),
            output_raw_sha256=sha(ro), output_markdown_sha256=sha(mo), changes=changes))
    receipt = dict(status='COMPLETE_DIAGNOSTIC_UNADOPTED', source=str(source),
        pages=len(records), tables=tables, changed_pages=sum(bool(r['changes']) for r in records),
        changed_blocks=sum(len(r['changes']) for r in records),
        changed_spans=sum(len(c['traces']) for r in records for c in r['changes']),
        new_model_calls=0, auxiliary_observations=0, runtime_GT=False,
        known_GT_hidden=True, network_isolated=True, wall_seconds=time.monotonic()-start,
        source_hashes={str(p):sha(p) for p in [Path(__file__),
            ROOT / 'code/research/phase2_math_delimiter_size_v1.py']},
        production_accepted=False, records=records, scans=scans)
    (out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['records', 'scans', 'source_hashes']}))


if __name__ == '__main__':
    main()
