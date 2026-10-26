"""Recompute current-source relations and bind all output bytes for list replay."""
from pathlib import Path
import sys

from phase2_final_runtime_v1 import ROOT, load, sha, verify_hashes


def verify_parallel_lists(folder, source, pages):
    sys.path.insert(0, str(ROOT/'code/research'))
    from parallel_candidate_0032_v2 import process
    from PIL import Image
    folder, source, pages = map(Path, [folder, source, pages])
    receipt = load(folder/'receipt.json')
    assert receipt['status'] == 'COMPLETE_CANDIDATE_NOT_SCORED'
    assert receipt['pages'] == 1651 and receipt['new_HTTP'] == 0
    assert receipt['GT_hidden'] and receipt['network_isolated'] and not receipt['runtime_GT']
    assert Path(receipt['source']).resolve() == source.resolve()
    verify_hashes(receipt['source_hashes'])
    assert receipt['source_hashes'][str(pages.resolve())] == sha(pages)
    manifest = {p['id']:p['image'] for p in load(pages)}
    records = receipt['records']
    assert len(records) == len(manifest) == 1651
    assert {r['page_evidence_only'] for r in records} == manifest.keys()
    for sub, ext in [('raw','.json'), ('markdown','.md')]:
        assert {p.stem for p in (folder/'predictions'/sub).glob('*'+ext)} == manifest.keys()
    for r in records:
        name = r['page_evidence_only']
        assert r['image'] == manifest[name] and sha(r['image']) == r['image_sha256']
        for sub, ext in [('raw','.json'), ('markdown','.md')]:
            assert sha(source/'predictions'/sub/(name+ext)) == r['input_'+sub+'_sha256']
            dest = folder/'predictions'/sub/(name+ext)
            assert not dest.is_symlink() and sha(dest) == r['output_'+sub+'_sha256']
        original = load(source/'predictions/raw'/(name+'.json'))
        with Image.open(r['image']) as image:
            expected, audit = process(image, original)
        changes = [a for a in audit if a['accepted']]
        assert changes == r['changes']
        assert [a for a in audit if not a['accepted']] == r['rejected']
        assert expected == load(folder/'predictions/raw'/(name+'.json'))
        markdown = (source/'predictions/markdown'/(name+'.md')).read_text()
        for change in changes:
            assert markdown.count(change['before']) == 1
            markdown = markdown.replace(change['before'], change['after'], 1)
        assert markdown == (folder/'predictions/markdown'/(name+'.md')).read_text()
        if not changes:
            for sub in ['raw','markdown']:
                assert r['input_'+sub+'_sha256'] == r['output_'+sub+'_sha256']
    assert receipt['changed_pages'] == sum(bool(r['changes']) for r in records)
    assert receipt['changed_groups'] == sum(len(c['groups']) for r in records for c in r['changes'])
    return receipt
