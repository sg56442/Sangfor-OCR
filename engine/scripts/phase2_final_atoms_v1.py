"""Audit the zero-inference table-atom stage against current input bytes."""
import copy
from pathlib import Path

from phase2_final_runtime_v1 import load, sha, verify_hashes
from phase2_table_atom_groups_v1 import transform


def verify_atoms(folder, source):
    folder, source = Path(folder), Path(source)
    receipt=load(folder/'receipt.json')
    assert receipt['status']=='COMPLETE_CANDIDATE_NOT_SCORED' and receipt['pages']==1651
    assert receipt['new_HTTP']==0 and receipt['GT_hidden'] and receipt['network_isolated']
    assert not receipt['runtime_GT'] and receipt['serialization_only']
    assert Path(receipt['source']).resolve()==source.resolve()
    verify_hashes(receipt['source_hashes'])
    records=receipt['records']
    ids={r['page_evidence_only'] for r in records}
    assert len(records)==len(ids)==1651
    for kind,ext in [('raw','.json'),('markdown','.md')]:
        assert {p.stem for p in (folder/'predictions'/kind).glob('*'+ext)}==ids
        for row in records:
            name=row['page_evidence_only']+ext
            assert sha(source/'predictions'/kind/name)==row['input_'+kind+'_sha256']
            assert sha(folder/'predictions'/kind/name)==row['output_'+kind+'_sha256']
            if not row['changes']:
                assert row['input_'+kind+'_sha256']==row['output_'+kind+'_sha256']
    for row in records:
        if not row['changes']:
            continue
        name=row['page_evidence_only']
        raw=load(source/'predictions/raw'/(name+'.json'))
        markdown=(source/'predictions/markdown'/(name+'.md')).read_text()
        for change in row['changes']:
            block=raw['blocks'][change['index']]
            assert block['type']=='table'
            before=block['content']
            after,trace=transform(before)
            assert trace==change['trace'] and after!=before and markdown.count(before)==1
            block['content']=after
            markdown=markdown.replace(before,after,1)
        assert raw==load(folder/'predictions/raw'/(name+'.json'))
        assert markdown==(folder/'predictions/markdown'/(name+'.md')).read_text()
    assert receipt['changed_pages']==sum(bool(r['changes']) for r in records)
    assert receipt['changed_blocks']==sum(len(r['changes']) for r in records)
    return receipt
