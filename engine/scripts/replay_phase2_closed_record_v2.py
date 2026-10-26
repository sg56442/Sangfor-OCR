"""Full-input zero-call diagnostic replay with exact raw/Markdown owner edits."""
import argparse,collections,json,os,subprocess,sys,time
from pathlib import Path
from phase2_final_runtime_v1 import ROOT,load,save,sha,now
sys.path[:0]=[str(ROOT/'code/research'),str(ROOT/'code/experimenter')]
from single_model_selective_v1 import hidden
from phase2_mixed_prose_runtime_v1 import owner_tokens
from repeated_runtime_0048b import patch
from spacing_apply_0046 import span
from phase2_closed_record_v2 import parse,candidate
from PIL import Image

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--inputs',required=True);ap.add_argument('--pages',required=True);ap.add_argument('--out',required=True);ap.add_argument('--isolated',action='store_true');args=ap.parse_args()
    if not args.isolated:
        subprocess.run(hidden(['unshare','--net',sys.executable,'-B',__file__,*sys.argv[1:],'--isolated']),check=True);return
    src,pages,out=map(lambda p:Path(p).resolve(),[args.inputs,args.pages,args.out]);assert out.is_relative_to(ROOT) and not out.exists();out.mkdir(parents=True)
    started=time.monotonic();counts=collections.Counter();records=[];bindings=[];changed=[]
    for sub in ['raw','markdown']:(out/'predictions'/sub).mkdir(parents=True)
    for row in load(pages):
        rp=src/'raw'/(row['id']+'.json');mp=src/'markdown'/(row['id']+'.md');rb,md=rp.read_bytes(),mp.read_bytes();raw=json.loads(rb);re=[];me=[];im=None
        bindings.append(dict(raw=str(rp),raw_sha256=sha(rp),markdown_sha256=sha(mp),source=row['image']))
        for i,b in enumerate(raw['blocks']):
            if b['type']!='table':continue
            counts['tables']+=1
            if parse(b.get('content')) is None:continue
            counts['markup_risks']+=1
            if im is None:im=Image.open(row['image']).convert('RGB')
            c,reason=candidate(im,b);counts[reason]+=1
            rec=dict(source=row['image'],source_sha256=sha(row['image']),raw=str(rp),owner=i,reason=reason,accepted=False);records.append(rec)
            if c is None:continue
            try:
                tokens=owner_tokens(rb,raw);red=(*tokens[(i,'content')],json.dumps(c['content'],ensure_ascii=False).encode());med=span(md,b['content'],c['content'])
                for edits,new in [(re,red),(me,med)]:assert all(not (new[0]<x[1] and new[1]>x[0]) for x in edits)
            except (AssertionError,ValueError,KeyError):rec['reason']='ambiguous_owner_bytes';continue
            re.append(red);me.append(med);rec.update(accepted=True,before=b['content'],candidate=c)
        nr,nm=patch(rb,re),patch(md,me)
        if (nr,nm)!=(rb,md):changed.append(row['id'])
        for sub,path,data in [('raw',rp,nr),('markdown',mp,nm)]:
            dest=out/'predictions'/sub/path.name
            if data==path.read_bytes():os.link(path,dest)
            else:dest.write_bytes(data)
        if im is not None:im.close()
    receipt=dict(at=now(),status='COMPLETE_DIAGNOSTIC',inputs=str(src),pages=len(bindings),pages_manifest=str(pages),pages_sha256=sha(pages),
        counts=dict(counts),records=records,bindings=bindings,changed_pages=changed,new_HTTP=0,GT_hidden=True,network_isolated=True,seconds=time.monotonic()-started,
        source_hashes={str(ROOT/name):sha(ROOT/name) for name in ['scripts/phase2_closed_record_v2.py','scripts/replay_phase2_closed_record_v2.py',
            'scripts/phase2_mixed_prose_runtime_v1.py','code/research/repeated_runtime_0048b.py','code/research/spacing_apply_0046.py']})
    save(out/'receipt.json',receipt);print({k:v for k,v in receipt.items() if k in ['status','pages','counts','changed_pages','seconds','new_HTTP']})

if __name__=='__main__':main()
