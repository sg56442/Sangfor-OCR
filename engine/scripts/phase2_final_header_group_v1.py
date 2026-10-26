"""Verify the zero-call source-compatible header-span tail from current source pixels and original bytes."""
import json
from pathlib import Path
import sys
import time

from phase2_final_runtime_v1 import ROOT, load, sha, verify_hashes

sys.path[:0] = [str(ROOT/'code/research'),str(ROOT/'code/experimenter')]
from header_runtime_0051b import raw_spans, patch
from header_group_0051b import lexical, candidate
from spacing_apply_0046 import span
from PIL import Image

RUNNER = 'code/research/header_runtime_0051b.py'


def verify_header(folder,source,pages,*,frozen=None):
    began = time.monotonic()
    folder,source,pages = map(Path,[folder,source,pages])
    receipt = load(folder/'receipt.json')
    assert Path(receipt['inputs'])==source and Path(receipt['manifest'])==pages
    assert receipt['manifest_sha256']==sha(pages)
    assert receipt['pages']==1651 and receipt['HTTP']==0
    assert receipt['GT_hidden'] and receipt['network_disabled']
    dependencies = load(folder/'dependencies.json')
    verify_hashes(dependencies)
    if frozen is not None:
        assert all(frozen['source_hashes'].get(p)==h for p,h in dependencies.items())
    manifest = load(pages)
    assert len(manifest)==len({p['id'] for p in manifest})==1651
    bindings = load(folder/'input_binding.json')
    expected_bindings,expected_records = {},[]
    changed_pages,changed_owners,total_tables = [],0,0
    expected_names = {p['id'] for p in manifest}
    for sub,ext in [('raw','json'),('markdown','md')]:
        assert {p.stem for p in (folder/'predictions'/sub).glob('*.'+ext)}==expected_names
    for index,row in enumerate(manifest):
        rp,mp = source/'raw'/(row['id']+'.json'),source/'markdown'/(row['id']+'.md')
        rb,md = rp.read_bytes(),mp.read_bytes()
        raw = json.loads(rb)
        expected_bindings[str(rp)]=sha(rp)
        expected_bindings[str(mp)]=sha(mp)
        redits,medits,seen = [],[],set()
        raw_map = None
        for owner,block in enumerate(raw['blocks']):
            if block['type']!='table':
                continue
            total_tables+=1
            old = block['content']
            decision = dict(accepted=False,reason='no_lexical_candidate',lexical=0)
            new,source_hash = old,None
            if lexical(old):
                source_hash=sha(row['image'])
                with Image.open(row['image']) as im:
                    im=im.convert('RGB');w,h=im.size
                    crop=im.crop(tuple(v*d for v,d in zip(block['bbox'],[w,h,w,h]))).rotate(block.get('angle',0),expand=True)
                    new,decision=candidate(crop,old)
            record = dict(manifest_index=index,owner=owner,decision=decision,applied=False,
                source_sha256=source_hash,before_sha256=__import__('hashlib').sha256(old.encode()).hexdigest(),
                after_sha256=__import__('hashlib').sha256(new.encode()).hexdigest())
            if new!=old and decision['accepted']:
                assert owner not in seen
                seen.add(owner)
                try:
                    if raw_map is None:
                        raw_map=raw_spans(rb,raw)
                    start,end,text=span(md,old,new)
                    rs,re_=raw_map[owner]
                    assert not any(start<e and end>s for s,e,_ in medits),'Overlapping Markdown owners'
                    assert not any(rs<e and re_>s for s,e,_ in redits),'Overlapping raw owners'
                except (AssertionError,KeyError) as error:
                    record['decision']=dict(accepted=False,reason='byte_binding_ambiguous',detail=str(error))
                else:
                    medits.append((start,end,text))
                    redits.append((rs,re_,json.dumps(new,ensure_ascii=b'\\u' in rb[rs:re_]).encode()))
                    record.update(applied=True,markdown_span=[start,end],raw_span=[rs,re_])
                    changed_owners+=1
            expected_records.append(record)
        if redits:
            changed_pages.append(index)
        for sub,path,data in [('raw',rp,patch(rb,redits)),('markdown',mp,patch(md,medits))]:
            actual=folder/'predictions'/sub/path.name
            assert actual.is_file() and not actual.is_symlink() and actual.read_bytes()==data
    assert bindings==expected_bindings
    assert receipt['records']==json.loads(json.dumps(expected_records))
    assert receipt['changed_pages']==changed_pages
    assert receipt['changed_owners']==changed_owners and receipt['tables']==total_tables
    return dict(HTTP=0,changed_pages=len(changed_pages),changed_owners=changed_owners,
                replay_seconds=receipt['wall_seconds'],verification_seconds=time.monotonic()-began)
