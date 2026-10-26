"""Portable pure post-selection; caller supplies current baseline and proposal."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from phase2_final_runtime_v1 import ROOT,GT,pure_command


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['baseline','candidate','pages','out']:
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--hidden',action='store_true')
    args=parser.parse_args()
    if not args.hidden:
        subprocess.run(pure_command([sys.executable,'-B',str(Path(__file__).resolve()),
                                    *sys.argv[1:],'--hidden']),check=True,cwd=ROOT)
        return
    assert all(not Path(p).exists() or Path(p).stat().st_size==0 for p in GT)
    from PIL import Image
    from phase2_resolution_retention_v1 import choose
    base,candidate,pages_path,out=[Path(getattr(args,k)).resolve() for k in ['baseline','candidate','pages','out']]
    assert all(p.is_relative_to(ROOT) for p in [base,candidate,pages_path,out]) and not out.exists()
    pages=json.loads(pages_path.read_text());ids={p['id'] for p in pages};assert len(pages)==len(ids)
    for pred in [base,candidate]:
        for sub,suffix in [('raw','.json'),('markdown','.md')]:
            assert {p.stem for p in (pred/sub).glob('*'+suffix)}==ids
    for sub in ['raw','markdown']:
        (out/'predictions'/sub).mkdir(parents=True)
    records=[];inputs={};began=time.monotonic()
    for page in pages:
        name=page['id'];bp=base/'raw'/(name+'.json');cp=candidate/'raw'/bp.name
        bm=base/'markdown'/(name+'.md');cm=candidate/'markdown'/bm.name
        before,after=json.loads(bp.read_text()),json.loads(cp.read_text())
        old_md,new_md=bm.read_text(),cm.read_text();raw=copy.deepcopy(after);md=new_md
        assert len(before['blocks'])==len(after['blocks'])
        changes=[];fallback=False
        for p in [bp,cp,bm,cm]:inputs[str(p)]=sha(p)
        indices=[i for i,(a,b) in enumerate(zip(before['blocks'],after['blocks'])) if a!=b]
        if indices:
            inputs[page['image']]=sha(page['image'])
            with Image.open(page['image']) as source:
                im=source.convert('RGB')
                for i in indices:
                    a,b=before['blocks'][i],after['blocks'][i]
                    assert a['type']==b['type']=='table'
                    assert {k:v for k,v in a.items() if k!='content'}=={k:v for k,v in b.items() if k!='content'}
                    decision=choose(im,before,after,i)
                    changes.append(dict(index=i,decision=decision))
                    if decision['accepted']:
                        continue
                    if md.count(b['content'])!=1:
                        fallback=True
                        break
                    raw['blocks'][i]['content']=a['content'];md=md.replace(b['content'],a['content'],1)
        if fallback:raw,md=copy.deepcopy(before),old_md
        rp,mp=out/'predictions/raw'/bp.name,out/'predictions/markdown'/bm.name
        if raw==before and md==old_md:
            os.link(bp,rp);os.link(bm,mp)
        elif raw==after and md==new_md:
            os.link(cp,rp);os.link(cm,mp)
        else:
            rp.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n');mp.write_text(md)
        records.append(dict(page_evidence_only=name,changed=md!=old_md,binding_fallback=fallback,
            changes=changes,raw_sha256=sha(rp),markdown_sha256=sha(mp)))
    assert all(sha(path)==digest for path,digest in inputs.items())
    deps=[Path(__file__),ROOT/'scripts/phase2_resolution_retention_v1.py',ROOT/'scripts/phase2_final_runtime_v1.py',
          ROOT/'code/research/table_mechanisms.py',ROOT/'code/research/phase2_local_cell_gate_0012.py',
          ROOT/'code/experimenter/source_cell_occupancy_v1.py',ROOT/'code/experimenter/table_partition_constraint_v1.py']
    receipt=dict(status='COMPLETE_UNADOPTED',decision='D0203',pages=len(records),
        changed_pages=sum(r['changed'] for r in records),binding_fallback_pages=sum(r['binding_fallback'] for r in records),
        selected_blocks=sum(c['decision']['accepted'] for r in records if not r['binding_fallback'] for c in r['changes']),
        model_calls=0,runtime_GT=False,known_GT_hidden=True,network_isolated=True,
        baseline=str(base),candidate=str(candidate),pages_sha256=sha(pages_path),
        input_hashes=inputs,source_hashes={str(p):sha(p) for p in deps},records=records,
        wall_seconds=time.monotonic()-began)
    (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['input_hashes','source_hashes','records']}))


if __name__=='__main__':
    main()
