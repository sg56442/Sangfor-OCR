"""Independent complete prediction replay. No score/inference; inputs explicit."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from phase2_math_prime_canonical_v1 import transform


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--predictions', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    start = time.monotonic()
    args.out.mkdir(parents=True, exist_ok=False)
    for kind in ('raw', 'markdown'):
        (args.out/'predictions'/kind).mkdir(parents=True)
    records = []
    for raw in sorted((args.predictions/'raw').glob('*.json')):
        md = args.predictions/'markdown'/(raw.stem+'.md')
        before = json.loads(raw.read_text())
        obj = json.loads(raw.read_text())
        block_changes = []
        for i, block in enumerate(obj['blocks']):
            content, changes = transform(block.get('content', ''))
            if changes:
                block['content'] = content
                block_changes.append({'index': i, 'changes': changes})
        old_md = md.read_text()
        new_md, md_changes = transform(old_md)
        raw_math = [(c['before'], c['after']) for b in block_changes for c in b['changes']]
        md_math = [(c['before'], c['after']) for c in md_changes]
        parity_fallback = sorted(raw_math) != sorted(md_math)
        if parity_fallback:
            obj = before
            block_changes = []
            md_changes = []
            new_md = old_md
        restored = json.loads(json.dumps(obj))
        for change in block_changes:
            i = change['index']
            restored['blocks'][i]['content'] = before['blocks'][i]['content']
        assert restored == before
        assert transform(new_md)[0] == new_md
        raw_out = args.out/'predictions/raw'/raw.name
        md_out = args.out/'predictions/markdown'/md.name
        raw_out.write_bytes((json.dumps(obj, ensure_ascii=False, indent=2)+'\n').encode() if block_changes else raw.read_bytes())
        md_out.write_bytes(new_md.encode() if md_changes else md.read_bytes())
        records.append({'page_evidence_only': raw.stem, 'raw_input_sha256': sha(raw),
                        'md_input_sha256': sha(md), 'raw_output_sha256': sha(raw_out),
                        'md_output_sha256': sha(md_out), 'blocks': block_changes,
                        'changed_math_spans': len(md_changes), 'raw_md_parity_fallback': parity_fallback})
    receipt = {'status': 'COMPLETE', 'input': str(args.predictions.resolve()),
               'pages': len(records), 'changed_pages': sum(bool(r['blocks']) for r in records),
               'changed_math_spans': sum(r['changed_math_spans'] for r in records),
               'extra_calls': 0, 'score_calls': 0, 'GT_read': False,
               'wall_seconds': time.monotonic()-start, 'oracle': '待测',
               'raw_structure_and_nonchanged_content_unchanged': True, 'idempotent': True,
               'source_sha256': {str(p): sha(p) for p in [Path(__file__), Path(__file__).with_name('phase2_math_prime_canonical_v1.py')]},
               'records': records}
    (args.out/'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(json.dumps({k:v for k,v in receipt.items() if k != 'records'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
