"""Full-input, zero-call source-grounded formula label serialization candidate."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from phase2_final_runtime_v1 import ROOT, GT, pure_command


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for key in ['input', 'pages', 'out']:
        ap.add_argument('--'+key, type=Path, required=True)
    ap.add_argument('--hidden', action='store_true')
    a = ap.parse_args()
    if not a.hidden:
        subprocess.run(pure_command([sys.executable, '-B', str(Path(__file__).resolve()),
            *sys.argv[1:], '--hidden']), cwd=ROOT, check=True)
        return
    assert all(not Path(p).exists() or Path(p).stat().st_size == 0 for p in GT)
    from PIL import Image
    from phase2_formula_label_v1 import split
    source, pages_path, out = map(Path.resolve, [a.input, a.pages, a.out])
    assert all(p.is_relative_to(ROOT) for p in [source, pages_path, out]) and not out.exists()
    pages = json.loads(pages_path.read_text())
    ids = {p['id'] for p in pages}
    assert len(ids) == len(pages)
    for kind, suffix in [('raw', '.json'), ('markdown', '.md')]:
        assert {p.stem for p in (source/kind).glob('*'+suffix)} == ids
        (out/'predictions'/kind).mkdir(parents=True)
    began, records, inputs = time.monotonic(), [], {}
    for page in pages:
        rp, mp = source/'raw'/(page['id']+'.json'), source/'markdown'/(page['id']+'.md')
        original = json.loads(rp.read_text())
        raw, old_md = copy.deepcopy(original), mp.read_text()
        md, blocks, changes, fallback = old_md, [], [], False
        inputs[str(rp)], inputs[str(mp)] = sha(rp), sha(mp)
        with Image.open(page['image']) as im:
            for i, block in enumerate(original['blocks']):
                parts, decision = split(im, block)
                if decision['applied']:
                    before, after = block['content'], parts[0]['content']+'\n\n'+parts[1]['content']
                    if md.count(before) != 1:
                        fallback = True
                        break
                    md = md.replace(before, after, 1)
                    inputs[page['image']] = sha(page['image'])
                    changes.append(dict(index=i, decision=decision, new_blocks=parts))
                blocks.extend(parts)
        raw['blocks'] = blocks
        if fallback:
            raw, md = original, old_md
        dest_rp, dest_mp = out/'predictions/raw'/rp.name, out/'predictions/markdown'/mp.name
        if raw == original and md == old_md:
            os.link(rp, dest_rp)
            os.link(mp, dest_mp)
        else:
            dest_rp.write_text(json.dumps(raw, ensure_ascii=False, indent=2)+'\n')
            dest_mp.write_text(md)
        records.append(dict(page_evidence_only=page['id'], changed=md != old_md,
            fallback=fallback, changes=changes, raw_sha256=sha(dest_rp), markdown_sha256=sha(dest_mp)))
    assert all(sha(p) == digest for p, digest in inputs.items())
    receipt = dict(status='COMPLETE_UNADOPTED', source=str(source), pages=len(pages),
        pages_sha256=sha(pages_path), changed_pages=sum(r['changed'] for r in records),
        changed_blocks=sum(len(r['changes']) for r in records if not r['fallback']),
        fallback_pages=sum(r['fallback'] for r in records), model_calls=0,
        GT_hidden=True, network_isolated=True, input_hashes=inputs, records=records,
        wall_seconds=time.monotonic()-began,
        source_hashes={str(p):sha(p) for p in [Path(__file__).resolve(),
            ROOT/'scripts/phase2_formula_label_v1.py', ROOT/'scripts/phase2_final_runtime_v1.py']})
    (out/'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['records', 'input_hashes', 'source_hashes']}))


if __name__ == '__main__':
    main()
