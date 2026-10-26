"""Full input zero-call repeated-line segmentation, preserving every occurrence."""
import argparse,json,os,subprocess,sys,time,re as regex,collections
from pathlib import Path
from phase2_final_runtime_v1 import ROOT,load,save,sha,now
sys.path[:0]=[str(ROOT/'code/research'),str(ROOT/'code/experimenter')]
from single_model_selective_v1 import hidden
from phase2_array_label_runtime_v1 import block_spans
from repeated_runtime_0048b import patch
from spacing_apply_0046 import span
from phase2_repeated_text_lines_v1 import parse,candidate
from PIL import Image

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--inputs',required=True);ap.add_argument('--pages',required=True);ap.add_argument('--out',required=True);ap.add_argument('--isolated',action='store_true');a=ap.parse_args()
    if not a.isolated:subprocess.run(hidden(['unshare','--net',sys.executable,'-B',__file__,*sys.argv[1:],'--isolated']),check=True);return
    source,pages,out=map(lambda p:Path(p).resolve(),[a.inputs,a.pages,a.out]);assert out.is_relative_to(ROOT) and not out.exists();out.mkdir(parents=True)
    began=time.monotonic();records=[];binding={};changed=[]
    for sub in ['raw','markdown']:(out/'predictions'/sub).mkdir(parents=True)
    manifest=load(pages);assert len(manifest)==1651
    for page in manifest:
        rp=source/'raw'/(page['id']+'.json');mp=source/'markdown'/(page['id']+'.md');rb,md=rp.read_bytes(),mp.read_bytes();raw=json.loads(rb);re=[];me=[];im=None;proposals=[]
        for p in [rp,mp]:binding[str(p)]=sha(p)
        for i,b in enumerate(raw['blocks']):
            if parse(b) is None:continue
            if im is None:im=Image.open(page['image'])
            c,reason=candidate(im,b);r=dict(source=page['image'],source_sha256=sha(page['image']),owner=i,reason=reason,applied=False);records.append(r)
            if c is None:continue
            proposals.append((i,b,c,r))
        groups=collections.defaultdict(list)
        for item in proposals:groups[item[1]['content']].append(item)
        for content,items in groups.items():
            try:
                all_owners=[i for i,b in enumerate(raw['blocks']) if b.get('content')==content]
                assert set(all_owners)=={i for i,b,c,r in items},'unverified_identical_owner'
                new={c['markdown'] for i,b,c,r in items};assert len(new)==1
                matches=list(regex.finditer(regex.escape(content.encode()),md));assert len(matches)==len(items),'ambiguous_duplicate_count'
                for match in matches:
                    before=md[:match.start()].rstrip(b' \t');after=md[match.end():].lstrip(b' \t')
                    assert not before or before.endswith((b'\n\n',b'\r\n\r\n')),'not_paragraph_start'
                    assert not after.strip() or after.startswith((b'\n\n',b'\r\n\r\n')),'not_paragraph_end'
                red=[];med=[];positions=block_spans(rb,raw)
                for i,b,c,r in items:red.append((*positions[i],b','.join(json.dumps(x,ensure_ascii=False).encode() for x in c['blocks'])))
                for match in matches:med.append((match.start(),match.end(),next(iter(new)).encode()))
                for edits,extra in [(re,red),(me,med)]:
                    for edit in extra:assert all(not(edit[0]<x[1] and edit[1]>x[0]) for x in edits)
            except (AssertionError,KeyError,ValueError) as e:
                for i,b,c,r in items:r['reason']='ambiguous_owner_group:'+str(e)
                continue
            re.extend(red);me.extend(med)
            for i,b,c,r in items:r.update(applied=True,before=b,candidate=c,group_size=len(items),all_occurrences_conserved=True)
        nr,nm=patch(rb,re),patch(md,me)
        if (nr,nm)!=(rb,md):changed.append(page['id'])
        for sub,p,data in [('raw',rp,nr),('markdown',mp,nm)]:
            dest=out/'predictions'/sub/p.name
            if data==p.read_bytes():os.link(p,dest)
            else:dest.write_bytes(data)
        if im is not None:im.close()
    save(out/'receipt.json',dict(at=now(),status='COMPLETE_DIAGNOSTIC',inputs=str(source),pages=1651,manifest=str(pages),manifest_sha256=sha(pages),bindings=binding,records=records,changed_pages=changed,new_HTTP=0,GT_hidden=True,network_isolated=True,seconds=time.monotonic()-began,source_hashes={str(ROOT/f):sha(ROOT/f) for f in ['scripts/phase2_repeated_text_lines_v1.py','scripts/replay_phase2_repeated_text_lines_v3.py']}))
    print(dict(changed_pages=changed,records=len(records),seconds=time.monotonic()-began))
if __name__=='__main__':main()
