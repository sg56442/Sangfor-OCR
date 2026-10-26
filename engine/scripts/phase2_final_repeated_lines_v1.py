"""Verify source-separated repeated lines and every preserved output byte."""
import collections,json,re,sys,time
from pathlib import Path
from PIL import Image
from phase2_final_runtime_v1 import ROOT,load,save,sha,verify_hashes
sys.path[:0]=[str(ROOT/'code/research'),str(ROOT/'code/experimenter')]
from phase2_repeated_text_lines_v1 import candidate,parse
from phase2_array_label_runtime_v1 import block_spans
from repeated_runtime_0048b import patch
RUNNER='scripts/replay_phase2_repeated_text_lines_v3.py'

def verify_lines(folder,source,pages):
    began=time.monotonic();folder,source,pages=map(Path,[folder,source,pages]);receipt=load(folder/'receipt.json')
    assert Path(receipt['inputs'])==source and Path(receipt['manifest'])==pages and sha(pages)==receipt['manifest_sha256']
    assert receipt['pages']==1651 and receipt['new_HTTP']==0 and receipt['GT_hidden'] and receipt['network_isolated']
    verify_hashes(receipt['source_hashes']);verify_hashes(receipt['bindings']);manifest=load(pages);assert len(manifest)==1651
    selected=[];changed=[]
    for page in manifest:
        rp=source/'raw'/(page['id']+'.json');mp=source/'markdown'/(page['id']+'.md');rb,md=rp.read_bytes(),mp.read_bytes();raw=json.loads(rb);groups=collections.defaultdict(list);im=None
        for i,b in enumerate(raw['blocks']):
            if parse(b) is None:continue
            if im is None:im=Image.open(page['image'])
            c,_=candidate(im,b)
            if c is not None:groups[b['content']].append((i,b,c))
        redit=[];medit=[]
        for old,items in groups.items():
            if {i for i,b,c in items}!={i for i,b in enumerate(raw['blocks']) if b.get('content')==old}:continue
            proposed={c['markdown'] for i,b,c in items}
            if len(proposed)!=1:continue
            matches=list(re.finditer(re.escape(old.encode()),md))
            if len(matches)!=len(items):continue
            try:
                positions=block_spans(rb,raw);er=[];em=[]
                for m in matches:
                    before=md[:m.start()].rstrip(b' \t');after=md[m.end():].lstrip(b' \t')
                    assert not before or before.endswith((b'\n\n',b'\r\n\r\n'))
                    assert not after.strip() or after.startswith((b'\n\n',b'\r\n\r\n'))
                    em.append((m.start(),m.end(),next(iter(proposed)).encode()))
                for i,b,c in items:er.append((*positions[i],b','.join(json.dumps(x,ensure_ascii=False).encode() for x in c['blocks'])))
                for edits,new in [(redit,er),(medit,em)]:
                    for edit in new:assert all(not(edit[0]<x[1] and edit[1]>x[0]) for x in edits)
            except (AssertionError,KeyError,ValueError):continue
            redit.extend(er);medit.extend(em);selected.extend((page['id'],i) for i,b,c in items)
        nr,nm=patch(rb,redit),patch(md,medit)
        assert re.sub(rb'\s+',b'',nm)==re.sub(rb'\s+',b'',md)
        assert (folder/'predictions/raw'/rp.name).read_bytes()==nr and (folder/'predictions/markdown'/mp.name).read_bytes()==nm
        if (rb,md)!=(nr,nm):changed.append(page['id'])
        if im is not None:im.close()
    assert changed==receipt['changed_pages'] and len(selected)==sum(r['applied'] for r in receipt['records'])
    assert all(len(list((folder/'predictions'/sub).iterdir()))==1651 for sub in ['raw','markdown'])
    return dict(HTTP=0,selected_owners=len(selected),changed_pages=changed,replay_seconds=receipt['seconds'],verification_seconds=time.monotonic()-began)

if __name__=='__main__':
    results={}
    for label in ['A_first','B_first','A_second','B_second']:
        folder=ROOT/f'runs/phase2_repeated_text_lines_{label}_v3';r=load(folder/'receipt.json');results[label]=verify_lines(folder,r['inputs'],r['manifest'])
    path=ROOT/'reports/rsi_phase2_repeated_lines_runtime_verified_v1.json';assert not path.exists()
    save(path,dict(status='PASS_ALL_FOUR_FULL_DOMAIN_RUNTIME_RECONSTRUCTIONS',results=results,verifier_sha256=sha(Path(__file__)),new_HTTP=0))
    print(results)
