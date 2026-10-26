"""Bind render-group output to a fresh deterministic replay of current input."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import time
import uuid

from phase2_final_runtime_v1 import ROOT, load, save, sha, verify_hashes, pure_command

RENDER_PYTHON = '/opt/p2t10/venv/bin/python'


def verify_render_groups(folder, source):
    folder, source = Path(folder).resolve(), Path(source).resolve()
    assert folder.is_relative_to(ROOT) and source.is_relative_to(ROOT)
    work = folder/('verification_'+uuid.uuid4().hex[:12])
    subprocess.run(pure_command([RENDER_PYTHON, '-B', str(Path(__file__).resolve()),
                    '--folder', str(folder), '--source', str(source), '--work', str(work)]),
                   cwd=ROOT, check=True, capture_output=True, text=True)
    result = load(work/'result.json')
    assert result['status'] == 'PASS' and result['new_HTTP'] == 0
    return load(folder/'receipt.json')


def check(folder, source, work):
    from phase2_math_groups_render_v4 import Renderer, transform, proposals
    start = time.monotonic()
    receipt = load(folder/'receipt.json')
    assert receipt['status'] == 'COMPLETE_CANDIDATE_NOT_SCORED'
    assert receipt['pages'] == 1651 and receipt['new_HTTP'] == 0
    assert receipt['GT_hidden'] and receipt['network_isolated'] and not receipt['runtime_GT']
    assert receipt['dynamic_current_input_renderer']
    assert Path(receipt['source']).resolve() == source
    verify_hashes(receipt['source_hashes'])
    records = receipt['records']
    ids = {r['page_evidence_only'] for r in records}
    assert len(records) == len(ids) == 1651
    assert not work.exists()
    work.mkdir()
    for sub, ext in [('raw','.json'), ('markdown','.md')]:
        assert {p.stem for p in (source/'predictions'/sub).glob('*'+ext)} == ids
        assert {p.stem for p in (folder/'predictions'/sub).glob('*'+ext)} == ids
        for row in records:
            name = row['page_evidence_only']+ext
            assert sha(source/'predictions'/sub/name) == row['input_'+sub+'_sha256']
            target = folder/'predictions'/sub/name
            assert not target.is_symlink() and sha(target) == row['output_'+sub+'_sha256']
    renderer = Renderer(work/'fresh_renders', maximum=512)
    pairs = set()
    for row in records:
        name = row['page_evidence_only']
        raw = load(source/'predictions/raw'/(name+'.json'))
        markdown = (source/'predictions/markdown'/(name+'.md')).read_text()
        for b in raw['blocks']:
            if b['type'] == 'table' and markdown.count(b.get('content','')) == 1:
                pairs.update(proposals(b.get('content','')))
    renderer.prepare(pairs)
    for row in records:
        name = row['page_evidence_only']
        raw = load(source/'predictions/raw'/(name+'.json'))
        markdown = (source/'predictions/markdown'/(name+'.md')).read_text()
        expected, changes = copy.deepcopy(raw), []
        for i,b in enumerate(expected['blocks']):
            if b['type'] != 'table':
                continue
            before = b.get('content','')
            after, trace = transform(before, renderer)
            assert transform(after, renderer)[0] == after
            if before == after or markdown.count(before) != 1:
                continue
            b['content'] = after
            markdown = markdown.replace(before, after, 1)
            changes.append(dict(index=i, trace=trace))
        assert changes == row['changes']
        assert expected == load(folder/'predictions/raw'/(name+'.json'))
        assert markdown == (folder/'predictions/markdown'/(name+'.md')).read_text()
        if not changes:
            for sub in ['raw','markdown']:
                assert row['input_'+sub+'_sha256'] == row['output_'+sub+'_sha256']
    assert receipt['changed_pages'] == sum(bool(r['changes']) for r in records)
    assert receipt['changed_blocks'] == sum(len(r['changes']) for r in records)
    save(work/'result.json', dict(status='PASS', pages=1651, new_HTTP=0,
        current_input_fresh_dynamic_render=True, source=str(source),
        receipt_sha256=sha(folder/'receipt.json'), wall_seconds=time.monotonic()-start))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--folder', required=True)
    ap.add_argument('--source', required=True)
    ap.add_argument('--work', required=True)
    a = ap.parse_args()
    values = [Path(p).resolve() for p in [a.folder,a.source,a.work]]
    assert all(p.is_relative_to(ROOT) for p in values)
    check(*values)
