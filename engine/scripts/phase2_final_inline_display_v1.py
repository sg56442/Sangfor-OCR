"""Recompute complete display ownership from current pixels and preserve all other bytes."""
from pathlib import Path
import sys

from phase2_final_runtime_v1 import ROOT, load, sha, verify_hashes


def verify_inline_display(destination, source, pages):
    sys.path.insert(0,str(ROOT/'code/research'))
    from inline_transform_0034_v1 import transform
    from inline_display_0034_v1 import parse,propose
    from PIL import Image
    destination,source,pages=map(lambda p:Path(p).resolve(),[destination,source,pages])
    r=load(destination/'receipt.json')
    assert r['pages']==1651 and r['HTTP']==r['tokens']==0
    assert r['GT_hidden'] and r['network_isolated'] and r['manifest_sha256']==sha(pages)
    verify_hashes(r['dependencies'])
    manifest={p['id']:p['image'] for p in load(pages)}
    assert len(r['records'])==1651 and {p['id'] for p in r['records']}==manifest.keys()
    for sub,ext in [('raw','.json'),('markdown','.md')]:
        assert {p.stem for p in (destination/sub).glob('*'+ext)}==manifest.keys()
    for row in r['records']:
        name=row['id'];assert row['source']==manifest[name] and sha(row['source'])==row['source_sha256']
        for sub,ext,key in [('raw','.json','raw'),('markdown','.md','md')]:
            p=destination/sub/(name+ext)
            assert not p.is_symlink() and sha(p)==row['output_'+key+'_sha256']
            assert sha(source/sub/(name+ext))==row['input_'+key+'_sha256']
        raw=load(source/'raw'/(name+'.json'));md=(source/'markdown'/(name+'.md')).read_text()
        indices=[i for i,b in enumerate(raw['blocks']) if b['type']=='text' and parse(b.get('content')or'')]
        expected,text,changes,audit=raw,md,[],[]
        if indices:
            with Image.open(row['source']) as image:
                expected,text,changes=transform(raw,md,image)
                audit=[dict(index=i,geometry=propose(image,raw['blocks'],i),unique_md=md.count(raw['blocks'][i]['content'])==1) for i in indices]
        assert changes==row['changes'] and audit==row['audit']
        assert expected==load(destination/'raw'/(name+'.json'))
        assert text==(destination/'markdown'/(name+'.md')).read_text()
        if not changes:
            for key in ['raw','md']:assert row['input_'+key+'_sha256']==row['output_'+key+'_sha256']
    assert r['changed_pages']==sum(bool(row['changes']) for row in r['records'])
    assert r['changed_owners']==sum(len(row['changes']) for row in r['records'])
    return r
