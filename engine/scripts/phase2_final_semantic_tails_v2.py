"""Verify complete semantic-tail materialization and original math conservation."""
import json
from pathlib import Path
import re
import time
from PIL import Image
from phase2_final_runtime_v1 import ROOT, load, save, sha, verify_hashes, now
from replay_phase2_semantic_tails_v2 import proposal
from phase2_array_label_runtime_v1 import block_spans
from connective_span_0069 import paragraph_span as span
from repeated_runtime_0048b import patch


def verify(source, output, pages):
    started = time.monotonic()
    source, output, pages = map(Path, [source, output, pages])
    receipt = load(output/'receipt.json')
    assert receipt['inputs'] == str(source.resolve())
    assert receipt['manifest_sha256'] == sha(pages)
    assert receipt['new_HTTP'] == 0 and receipt['GT_hidden'] and receipt['network_isolated']
    verify_hashes(receipt['code_hashes'])
    verify_hashes(receipt['bindings'])
    selected, changed, brace_count = [], [], 0
    for page in load(pages):
        rp, mp = source/'raw'/(page['id']+'.json'), source/'markdown'/(page['id']+'.md')
        rb, md = rp.read_bytes(), mp.read_bytes()
        raw = json.loads(rb)
        red, med, images = [], [], []
        positions, page_braces = None, 0
        def image():
            if not images:
                images.append(Image.open(page['image']))
            return images[0]
        for index, block in enumerate(raw['blocks']):
            replacement, reason, rule, geometry = proposal(block, image)
            if replacement is None or rule == 'brace' and (brace_count >= 8 or page_braces >= 4):
                continue
            try:
                edit = span(md, block['content'], replacement['content'])
                assert all(not(edit[0] < e and edit[1] > s) for s, e, _ in med)
                if rule == 'brace':
                    assert md.count(block['content'].encode()) == 1
                    assert not md[:edit[0]] or md[:edit[0]].endswith((b'\n\n', b'\r\n\r\n'))
                    assert not md[edit[1]:].strip() or md[edit[1]:].startswith((b'\n\n', b'\r\n\r\n'))
                if positions is None:
                    positions = block_spans(rb, raw)
            except (AssertionError, KeyError, ValueError):
                continue
            # Each original math chunk survives verbatim and in source order.
            bodies = re.findall(r'\\\((.*?)\\\)', block['content'] if rule == 'brace' else replacement['content'], re.S)
            containing = replacement['content'] if rule == 'brace' else block['content']
            cursor = 0
            for body in bodies:
                found = containing.find(body, cursor)
                assert found >= cursor, (page['id'], index, rule, 'math body lost or reordered')
                cursor = found + len(body)
            assert {k:v for k,v in block.items() if k not in ['type','content']} == {k:v for k,v in replacement.items() if k not in ['type','content']}
            red.append((*positions[index], json.dumps(replacement, ensure_ascii=False).encode()))
            med.append(edit)
            selected.append(dict(page=page['id'], owner=index, rule=rule, math_chunks=len(bodies), source_sha256=sha(page['image'])))
            if rule == 'brace':
                brace_count += 1
                page_braces += 1
        nr, nm = patch(rb, red), patch(md, med)
        for kind, origin, data in [('raw', rp, nr), ('markdown', mp, nm)]:
            dest = output/'predictions'/kind/origin.name
            assert dest.is_file() and not dest.is_symlink() and dest.read_bytes() == data, dest
        if (nr, nm) != (rb, md):
            changed.append(page['id'])
        for im in images:
            im.close()
    assert len(load(pages)) == 1651
    assert all(len(list((output/'predictions'/sub).iterdir())) == 1651 for sub in ['raw','markdown'])
    assert changed == receipt['changed_pages']
    assert [(v['page'],v['owner'],v['rule']) for v in selected] == [(v['page'],v['owner'],v['rule']) for v in receipt['records'] if v['applied']]
    return dict(pages=1651, changed_pages=changed, selected=selected, new_HTTP=0,
                receipt_sha256=sha(output/'receipt.json'), replay_seconds=receipt['seconds'],
                verification_seconds=time.monotonic()-started)


if __name__ == '__main__':
    results = {}
    for label in ['A_first','B_first','A_second','B_second']:
        output = ROOT/f'runs/phase2_semantic_prose_{label}_v2'
        receipt = load(output/'receipt.json')
        results[label] = verify(receipt['inputs'], output, receipt['manifest'])
    save(ROOT/'reports/rsi_phase2_semantic_prose_combinations_verified_v2.json',
         dict(status='PASS_ALL_FOUR_EXACT_RECONSTRUCTIONS', at=now(), results=results, new_HTTP=0,
              scope='Zero-call tails only. B prose responses require independent protocol/cost/selection verification.',
              verifier_sha256=sha(Path(__file__))))
    print({k:dict(changed_pages=len(v['changed_pages']), verification_seconds=v['verification_seconds']) for k,v in results.items()})
