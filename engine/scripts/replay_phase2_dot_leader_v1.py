#!/usr/bin/env python3
"""Full input-only replay of the unadopted dot-leader structure proposal."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
GT = ['/opt/p2t10/hidden/OmniDocBench.json',
      '/opt/p2t10/hidden/source_validation_v2_references.jsonl',
      '/opt/p2t10/hidden/source_validation_v1_references.jsonl']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--hidden', action='store_true')
    args = parser.parse_args()
    if not args.hidden:
        hidden = [p for p in GT if Path(p).exists()]
        shell = 'set -euo pipefail\nn="$1"; shift\nfor ((i=0;i<n;i++)); do mount --bind /dev/null "$1"; test ! -s "$1"; shift; done\nexec "$@"'
        subprocess.run(['unshare', '--net', '--mount', '--propagation', 'private', '/bin/bash',
                        '-c', shell, 'phase2-dot-leader', str(len(hidden)), *hidden,
                        sys.executable, '-B', str(Path(__file__).resolve()), *sys.argv[1:], '--hidden'],
                       check=True, cwd=ROOT, env=dict(os.environ, CUDA_VISIBLE_DEVICES='',
                       OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1'))
        return
    assert all(not Path(p).exists() or Path(p).stat().st_size == 0 for p in GT)
    from PIL import Image
    from phase2_dot_leader_structure_v1 import transform
    source, out = Path(args.source).resolve(), Path(args.out).resolve()
    assert source.is_relative_to(ROOT) and out.is_relative_to(ROOT) and not out.exists()
    manifest = ROOT / 'code/runtime/runs/native_full1651_gpu5_v2/pages.json'
    pages = json.loads(manifest.read_text())
    assert len(pages) == 1651
    for sub in ['raw', 'markdown']:
        (out / 'predictions' / sub).mkdir(parents=True)
    records, scans, start = [], [], time.monotonic()
    for page in pages:
        rp = source / 'predictions/raw' / (page['id'] + '.json')
        mp = source / 'predictions/markdown' / (page['id'] + '.md')
        original = json.loads(rp.read_text())
        raw = copy.deepcopy(original)
        markdown = mp.read_text()
        changes = []
        for index, block in enumerate(raw['blocks']):
            if block.get('type') != 'table':
                continue
            before = block.get('content', '')
            if '...' not in before:
                continue
            with Image.open(page['image']) as image:
                rect = tuple(round(v*(image.width if i % 2 == 0 else image.height))
                             for i, v in enumerate(block['bbox']))
                after, evidence = transform(image.crop(rect), before)
            scans.append(dict(page_evidence_only=page['id'], index=index, evidence=evidence))
            if after == before:
                continue
            # Duplicate serializations would make literal replacement ambiguous.
            if markdown.count(before) != 1:
                scans[-1]['composition_rejected'] = 'ambiguous_markdown_owner'
                continue
            block['content'] = after
            markdown = markdown.replace(before, after, 1)
            changes.append(dict(index=index, source_rect=rect, before=before, after=after,
                                source_image_sha256=sha(page['image']), evidence=evidence))
        restored = copy.deepcopy(raw)
        for change in changes:
            restored['blocks'][change['index']] = original['blocks'][change['index']]
        assert restored == original
        ro = out / 'predictions/raw' / rp.name
        mo = out / 'predictions/markdown' / mp.name
        if changes:
            ro.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n')
            mo.write_text(markdown)
        else:
            os.link(rp, ro)
            os.link(mp, mo)
        records.append(dict(page_evidence_only=page['id'], input_raw_sha256=sha(rp),
                            input_markdown_sha256=sha(mp), output_raw_sha256=sha(ro),
                            output_markdown_sha256=sha(mo), changes=changes))
    receipt = dict(status='COMPLETE_DIAGNOSTIC_UNADOPTED', source=str(source), pages=len(records),
                   changed_pages=sum(bool(x['changes']) for x in records),
                   changed_blocks=sum(len(x['changes']) for x in records),
                   new_model_calls=0, auxiliary_observations=0, runtime_GT=False, GT_hidden=True,
                   network_isolated=True, wall_seconds=time.monotonic()-start,
                   source_hashes={str(p): sha(p) for p in [Path(__file__),
                       ROOT/'scripts/phase2_dot_leader_structure_v1.py', manifest]},
                   existing_character_stream_and_row_order_preserved=True,
                   production_accepted=False, records=records, scans=scans)
    (out/'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['records','scans','source_hashes']}))


if __name__ == '__main__':
    main()
