"""Fixed connective and source-brace tails; zero calls and complete byte binding."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from PIL import Image
from phase2_final_runtime_v1 import ROOT, load, save, sha, now
from phase2_connective_math_v2 import convert
from phase2_outer_brace_v1 import transform
from phase2_array_label_runtime_v1 import block_spans
sys.path[:0] = [str(ROOT/'code/research'), str(ROOT/'code/experimenter')]
from single_model_selective_v1 import hidden, HIDDEN
from connective_span_0069 import paragraph_span as span
from repeated_runtime_0048b import patch


def proposal(block, image):
    if block.get('type') == 'equation' and isinstance(block.get('content'), str):
        new, reason = convert(block['content'])
        return (dict(block, type='text', content=new) if new is not None else None), reason, 'connective', None
    content = block.get('content')
    if block.get('type') == 'text' and isinstance(content, str) and content.count('\\begin{cases}') >= 2 and '\n\n' in content:
        candidate, reason = transform(image(), block)
        return (dict(block, type='equation', content=candidate['content']) if candidate else None), reason, 'brace', candidate
    return None, 'not_candidate', None, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['inputs', 'pages', 'out']:
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--isolated', action='store_true')
    args = parser.parse_args()
    if not args.isolated:
        subprocess.run(hidden(['unshare', '--net', sys.executable, '-B', __file__, *sys.argv[1:], '--isolated']), check=True)
        return
    assert all(Path(p).stat().st_size == 0 for p in HIDDEN)
    source, pages, out = [Path(v).resolve() for v in [args.inputs, args.pages, args.out]]
    assert source.is_relative_to(ROOT) and out.is_relative_to(ROOT) and not out.exists()
    out.mkdir(parents=True)
    started = time.monotonic()
    manifest = load(pages)
    assert len(manifest) == len({p['id'] for p in manifest}) == 1651
    for kind in ['raw', 'markdown']:
        (out/'predictions'/kind).mkdir(parents=True)
    bindings, records, changed = {}, [], []
    brace_count = 0
    for page in manifest:
        rp, mp = source/'raw'/(page['id']+'.json'), source/'markdown'/(page['id']+'.md')
        rb, md = rp.read_bytes(), mp.read_bytes()
        raw = json.loads(rb)
        bindings[str(rp)], bindings[str(mp)] = sha(rp), sha(mp)
        raw_edits, md_edits, images = [], [], []
        positions, page_braces = None, 0
        def image():
            if not images:
                images.append(Image.open(page['image']))
                bindings[page['image']] = sha(page['image'])
            return images[0]
        for index, block in enumerate(raw['blocks']):
            replacement, reason, rule, geometry = proposal(block, image)
            if replacement is None:
                continue
            record = dict(page=page['id'], source=page['image'], source_sha256=sha(page['image']), owner=index,
                          before=block, after=replacement, applied=False, reason=reason, rule=rule, geometry=geometry)
            records.append(record)
            if rule == 'brace' and (brace_count >= 8 or page_braces >= 4):
                record['reason'] = 'edit_budget'
                continue
            try:
                edit = span(md, block['content'], replacement['content'])
                assert all(not(edit[0] < e and edit[1] > s) for s, e, _ in md_edits)
                if rule == 'brace':
                    assert md.count(block['content'].encode()) == 1
                    assert not md[:edit[0]] or md[:edit[0]].endswith((b'\n\n', b'\r\n\r\n'))
                    assert not md[edit[1]:].strip() or md[edit[1]:].startswith((b'\n\n', b'\r\n\r\n'))
                if positions is None:
                    positions = block_spans(rb, raw)
                raw_edits.append((*positions[index], json.dumps(replacement, ensure_ascii=False).encode()))
                md_edits.append(edit)
                record['applied'] = True
                if rule == 'brace':
                    brace_count += 1
                    page_braces += 1
            except (AssertionError, KeyError, ValueError) as error:
                record['reason'] = 'ambiguous_binding:'+str(error)
        nr, nm = patch(rb, raw_edits), patch(md, md_edits)
        if (nr, nm) != (rb, md):
            changed.append(page['id'])
        for kind, origin, data in [('raw', rp, nr), ('markdown', mp, nm)]:
            destination = out/'predictions'/kind/origin.name
            if data == origin.read_bytes():
                os.link(origin, destination)
            else:
                destination.write_bytes(data)
        for im in images:
            im.close()
    report = dict(status='COMPLETE_FIXED_RULE_REPLAY', at=now(), inputs=str(source), manifest=str(pages),
                  manifest_sha256=sha(pages), pages=1651, bindings=bindings, records=records,
                  changed_pages=changed, new_HTTP=0, GT_hidden=True, network_isolated=True,
                  seconds=time.monotonic()-started, brace_edit_cap=8, brace_per_page_cap=4,
                  code_hashes={str(ROOT/p):sha(ROOT/p) for p in
                  ['scripts/phase2_connective_math_v1.py', 'scripts/phase2_connective_math_v2.py',
                   'scripts/phase2_outer_brace_v1.py', 'code/research/outer_brace_0068_v3.py', 'code/research/connective_span_0069.py',
                   'scripts/replay_phase2_semantic_tails_v2.py']})
    save(out/'receipt.json', report)
    print(dict(changed_pages=len(changed), proposed=len(records), applied=sum(r['applied'] for r in records), seconds=report['seconds']))


if __name__ == '__main__':
    main()
