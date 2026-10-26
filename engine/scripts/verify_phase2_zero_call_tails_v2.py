"""Reconstruct exact source-bound list or closed-record output on every page."""
import json,sys,time
from pathlib import Path
from PIL import Image
from phase2_final_runtime_v1 import ROOT,load,save,sha,verify_hashes
sys.path[:0]=[str(ROOT/'code/research'),str(ROOT/'code/experimenter')]
from list_columns_0060_v2 import candidate as list_candidate
from phase2_closed_record_v2 import candidate as closed_candidate
from phase2_mixed_prose_runtime_v1 import owner_tokens
from phase2_array_label_runtime_v1 import block_spans
from repeated_runtime_0048b import patch
from spacing_apply_0046 import span

def verify_tail(source,target,pages,kind):
    began=time.monotonic();source,target,pages=map(Path,[source,target,pages]);assert kind in ['list','closed']
    manifest=load(pages);assert len(manifest)==1651
    changed=[];selected=[]
    for row in manifest:
        name=row['id'];rp=source/'raw'/(name+'.json');mp=source/'markdown'/(name+'.md');rb,md=rp.read_bytes(),mp.read_bytes();raw=json.loads(rb);re=[];me=[];im=None
        for i,b in enumerate(raw['blocks']):
            if b.get('type')!='table':continue
            if im is None:im=Image.open(row['image'])
            c,reason=(list_candidate if kind=='list' else closed_candidate)(im,b)
            if c is None:continue
            new=c['text'] if kind=='list' else c['content']
            try:
                med=span(md,b['content'],new)
                if kind=='list':
                    positions=block_spans(rb,raw);red=(*positions[i],json.dumps(dict(b,type='text',content=new),ensure_ascii=False).encode())
                else:
                    positions=owner_tokens(rb,raw);red=(*positions[(i,'content')],json.dumps(new,ensure_ascii=False).encode())
                    for edits,edit in [(re,red),(me,med)]:assert all(not (edit[0]<x[1] and edit[1]>x[0]) for x in edits)
            except (AssertionError,KeyError,ValueError):continue
            re.append(red);me.append(med);selected.append(dict(source=row['image'],source_sha256=sha(row['image']),owner=i))
        nr,nm=patch(rb,re),patch(md,me)
        for sub,path,data in [('raw',rp,nr),('markdown',mp,nm)]:
            dest=target/sub/path.name;assert dest.is_file() and not dest.is_symlink() and dest.read_bytes()==data,(kind,dest)
        if (nr,nm)!=(rb,md):changed.append(name)
        if im is not None:im.close()
    assert all(len(list((target/sub).iterdir()))==1651 for sub in ['raw','markdown'])
    return dict(pages=1651,changed_pages=changed,selected=selected,verification_seconds=time.monotonic()-began,new_HTTP=0)

if __name__=='__main__':
    pages=ROOT/'code/runtime/runs/native_full1651_gpu5_v2/pages.json';results={}
    for label in ['A_first','B_first','A_second','B_second']:
        folder=ROOT/('runs/phase2_column_list_closed_'+label+'_v1');r=load(folder/'receipt.json');verify_hashes(r['source_hashes'])
        assert r['new_HTTP']==0 and r['GT_hidden'] and r['network_isolated'] and r['pages']==1651
        results[label]=verify_tail(r['inputs'],folder/'predictions',pages,'closed')
        results[label]['replay_seconds']=r['seconds'];results[label]['receipt_sha256']=sha(folder/'receipt.json')
    save(ROOT/'reports/rsi_phase2_column_list_closed_inputs_verified_v2.json',dict(status='PASS_ALL_FOUR_EXACT_RECONSTRUCTIONS',results=results,new_HTTP=0))
