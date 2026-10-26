"""Bind the added zero-call source-supported dot-leader stage to current input."""
import copy
from pathlib import Path
from lxml import html
from phase2_final_runtime_v1 import load, sha, verify_hashes


def verify_dot_leaders(folder, source, pages):
    folder, source, pages = map(Path, [folder, source, pages])
    receipt = load(folder/'receipt.json')
    assert receipt['status'] == 'COMPLETE_DIAGNOSTIC_UNADOPTED'
    assert receipt['pages'] == 1651 and receipt['new_model_calls'] == receipt['auxiliary_observations'] == 0
    assert receipt['GT_hidden'] and receipt['network_isolated'] and not receipt['runtime_GT']
    assert Path(receipt['source']).resolve() == source.resolve()
    assert receipt['source_hashes'][str(pages.resolve())] == sha(pages)
    verify_hashes(receipt['source_hashes'])
    ids = {p['id'] for p in load(pages)}
    rows = receipt['records']
    assert len(rows) == len(ids) == 1651 and {r['page_evidence_only'] for r in rows} == ids
    for kind, ext in [('raw','.json'),('markdown','.md')]:
        assert {p.stem for p in (folder/'predictions'/kind).glob('*'+ext)} == ids
        for row in rows:
            name = row['page_evidence_only']+ext
            assert sha(source/'predictions'/kind/name) == row['input_'+kind+'_sha256']
            assert sha(folder/'predictions'/kind/name) == row['output_'+kind+'_sha256']
    for row in rows:
        name = row['page_evidence_only']
        original = load(source/'predictions/raw'/(name+'.json'))
        expected = copy.deepcopy(original)
        markdown = (source/'predictions/markdown'/(name+'.md')).read_text()
        for change in row['changes']:
            i = change['index']
            assert original['blocks'][i]['type'] == 'table'
            assert original['blocks'][i]['content'] == change['before']
            assert change['evidence']['selected']
            before, after = html.fromstring(change['before']), html.fromstring(change['after'])
            assert ''.join(before.itertext()) == ''.join(after.itertext())
            assert len(before.xpath('./tr|./tbody/tr')) == len(after.xpath('./tr|./tbody/tr'))
            assert markdown.count(change['before']) == 1
            expected['blocks'][i]['content'] = change['after']
            markdown = markdown.replace(change['before'], change['after'], 1)
        assert load(folder/'predictions/raw'/(name+'.json')) == expected
        assert (folder/'predictions/markdown'/(name+'.md')).read_text() == markdown
    assert receipt['changed_pages'] == sum(bool(r['changes']) for r in rows)
    assert receipt['changed_blocks'] == sum(len(r['changes']) for r in rows)
    return receipt
