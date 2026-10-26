"""GT-hidden zero-call replay; preserve untouched bytes and literal owner binding."""
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
from replay_phase2_dot_leader_v2 import GT


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
        subprocess.run(['unshare', '--net', '--mount', '--propagation', 'private',
                        '/bin/bash', '-c', shell, 'atom-groups', str(len(hidden)), *hidden,
                        sys.executable, '-B', str(Path(__file__).resolve()),
                        *sys.argv[1:], '--hidden'], check=True, cwd=ROOT,
                       env=dict(os.environ, CUDA_VISIBLE_DEVICES='',
                                PYTHONDONTWRITEBYTECODE='1'))
        return
    assert all(not Path(p).exists() or Path(p).stat().st_size == 0 for p in GT)
    from phase2_table_atom_groups_v1 import transform
    source, out = Path(args.source).resolve(), Path(args.out).resolve()
    assert source.is_relative_to(ROOT) and out.is_relative_to(ROOT) and not out.exists()
    files = sorted((source/'predictions/raw').glob('*.json'))
    assert len(files) == 1651
    for sub in ['raw', 'markdown']:
        (out/'predictions'/sub).mkdir(parents=True)
    records, start = [], time.monotonic()
    for rp in files:
        mp = source/'predictions/markdown'/(rp.stem+'.md')
        original = json.loads(rp.read_text())
        raw, markdown, changes = copy.deepcopy(original), mp.read_text(), []
        for index, block in enumerate(raw['blocks']):
            if block.get('type') != 'table':
                continue
            before = block.get('content', '')
            after, trace = transform(before)
            assert transform(after)[0] == after
            if before == after or markdown.count(before) != 1:
                continue
            block['content'] = after
            markdown = markdown.replace(before, after, 1)
            changes.append(dict(index=index, trace=trace))
        restored = copy.deepcopy(raw)
        for change in changes:
            restored['blocks'][change['index']] = original['blocks'][change['index']]
        assert restored == original
        ro, mo = out/'predictions/raw'/rp.name, out/'predictions/markdown'/mp.name
        if changes:
            ro.write_text(json.dumps(raw, ensure_ascii=False, indent=2)+'\n')
            mo.write_text(markdown)
        else:
            os.link(rp, ro)
            os.link(mp, mo)
        records.append(dict(page_evidence_only=rp.stem, changes=changes,
                            input_raw_sha256=sha(rp), input_markdown_sha256=sha(mp),
                            output_raw_sha256=sha(ro), output_markdown_sha256=sha(mo)))
    receipt = dict(status='COMPLETE_CANDIDATE_NOT_SCORED', source=str(source),
                   pages=1651, changed_pages=sum(bool(r['changes']) for r in records),
                   changed_blocks=sum(len(r['changes']) for r in records),
                   new_HTTP=0, runtime_GT=False, GT_hidden=True, network_isolated=True,
                   serialization_only=True, character_or_structure_recovery=False,
                   wall_seconds=time.monotonic()-start, records=records,
                   source_hashes={str(p):sha(p) for p in [Path(__file__),
                       ROOT/'scripts/phase2_table_atom_groups_v1.py']})
    (out/'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['records','source_hashes']}))


if __name__ == '__main__':
    main()
