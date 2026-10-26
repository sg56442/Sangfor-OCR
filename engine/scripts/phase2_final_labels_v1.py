"""Verify the complete current-input, zero-call formula-label stage."""
from pathlib import Path
from phase2_final_runtime_v1 import load, sha, verify_hashes


def verify_labels(folder, source, pages):
    folder, source, pages = map(Path, [folder, source, pages])
    receipt = load(folder/'receipt.json')
    assert receipt['status'] == 'COMPLETE_UNADOPTED'
    assert receipt['pages'] == 1651 and receipt['model_calls'] == 0
    assert receipt['GT_hidden'] and receipt['network_isolated']
    assert Path(receipt['source']).resolve() == source.resolve()
    assert receipt['pages_sha256'] == sha(pages)
    verify_hashes(receipt['source_hashes'])
    verify_hashes(receipt['input_hashes'])
    records = receipt['records']
    ids = {p['id'] for p in load(pages)}
    assert len(records) == len(ids) == 1651
    assert {r['page_evidence_only'] for r in records} == ids
    for sub, suffix in [('raw', '.json'), ('markdown', '.md')]:
        assert {p.stem for p in (folder/'predictions'/sub).glob('*'+suffix)} == ids
        for row in records:
            assert sha(folder/'predictions'/sub/(row['page_evidence_only']+suffix)) == row[sub+'_sha256']
    for row in records:
        name = row['page_evidence_only']
        original = load(source/'raw'/(name+'.json'))
        output = load(folder/'predictions/raw'/(name+'.json'))
        expected = []
        by_index = {c['index']:c for c in row['changes']} if not row['fallback'] else {}
        markdown = (source/'markdown'/(name+'.md')).read_text()
        for i, block in enumerate(original['blocks']):
            change = by_index.get(i)
            if change is None:
                expected.append(block)
                continue
            label, equation = change['new_blocks']
            decision = change['decision']
            assert label['type'] == 'text' and equation['type'] == 'equation'
            assert label['content'] == decision['label']
            assert equation['content'][2:-2] == decision['original_body']
            assert decision['original_prefix']+decision['original_body']+'\\]' == block['content']
            a, b, c = block['bbox'], label['bbox'], equation['bbox']
            assert b[:2] == a[:2] and c[1:] == [a[1], a[2], a[3]]
            assert b[3] == a[3] and b[2] == c[0] and a[0] < b[2] < a[2]
            assert markdown.count(block['content']) == 1
            markdown = markdown.replace(block['content'], label['content']+'\n\n'+equation['content'], 1)
            expected.extend([label, equation])
        assert output == dict(original, blocks=expected)
        assert (folder/'predictions/markdown'/(name+'.md')).read_text() == markdown
    return receipt
