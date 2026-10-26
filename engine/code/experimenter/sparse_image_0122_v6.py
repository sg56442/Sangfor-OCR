"""Current-input-only sparse image formula pipeline. No historical response input."""
import argparse
import collections
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'code/experimenter'),str(ROOT/'scripts'),str(ROOT/'code/runtime'),str(ROOT/'code/research')]
from sparse_image_0122_support_v6 import load,save,sha,check_binding,admitted,audit_usage
from panel_admission_0112_v2 import input_digest
from dependency_lock_0111_v1 import create,verify
from finite_request_identity_0101_v1 import prepare,pix,key,helper,valid_record
from census_phase2_sparse_image_v1 import features
from phase2_sparse_relation_v1 import relation_features
from phase2_sparse_equation_gate_v1 import gate
from PIL import Image
from mineru_vl_utils.structs import ContentBlock

ENTRIES=['code/experimenter/sparse_image_0122_v6.py','code/experimenter/sparse_image_0122_worker_v6.py','scripts/processor_replay_stream_v1.py']

def safe_out(p):
    p=Path(p).absolute(); assert not p.is_symlink()
    assert p.resolve().parent==ROOT/'runs', 'Run must be a direct campaign runs child'
    return p.resolve()

def request(c,rect,task,**extra):
    with Image.open(c['source']) as im: prepared=prepare(im.convert('RGB').crop(rect),task)
    return dict(ordinal=c['ordinal'],rect=rect,task=task,identity_key=key(prepared.size,pix(prepared),task),**extra)

def initialize(a,out):
    inputs=Path(a.inputs).resolve(); image_dir=Path(a.image_dir).resolve()
    assert inputs.is_dir() and image_dir.is_dir()
    ids=sorted(p.stem for p in (inputs/'raw').glob('*.json'))
    assert ids and len(ids)==len(set(ids))
    assert {p.stem for p in (inputs/'markdown').glob('*.md')}==set(ids)
    files=collections.defaultdict(list)
    for p in image_dir.iterdir():
        if p.is_file() and p.suffix.lower() in ['.png','.jpg','.jpeg','.webp','.tif','.tiff','.bmp']:files[p.stem].append(p.resolve())
    pages=[]
    for name in ids:
        assert len(files[name])==1, 'Missing/ambiguous image stem: '+name
        pages.append(dict(id=name,image=str(files[name][0])))
    cfg=dict(inputs=str(inputs),image_dir=str(image_dir),gpus=a.gpus,caps=dict(total=a.cap,layout=a.layout_cap,formula=a.formula_cap,source=a.source_cap,owner=a.owner_cap),version='sparse_image_0122_v6')
    assert 0<=a.cap<=48 and 0<=a.layout_cap<=48 and 0<=a.formula_cap<=48
    assert 1<=a.source_cap<=6 and 1<=a.owner_cap<=3
    assert a.gpus and len(set(a.gpus))==len(a.gpus) and set(a.gpus)<={0,1,3}
    if (out/'admission_binding.json').exists():
        assert load(out/'runtime_inputs.json')==cfg, 'Initialize conflict'
        check_binding(out);print('ALREADY_INITIALIZED');return
    out.mkdir(exist_ok=True)
    if (out/'runtime_inputs.json').exists():assert load(out/'runtime_inputs.json')==cfg
    save(out/'runtime_inputs.json',cfg);save(out/'input_manifest.json',pages)
    command=[sys.executable,'-B',__file__,'census','--out',str(out),'--hidden']
    from panel_hidden_0110_v2 import restricted
    subprocess.run(restricted(out,['unshare','--net',*command]),check=True)

def census(out):
    assert not (out/'admission_binding.json').exists(), 'Immutable census: no budget reset'
    start=time.monotonic(); cfg=load(out/'runtime_inputs.json'); inputs=Path(cfg['inputs']);pages=load(out/'input_manifest.json')
    records=[]; bindings=[]
    for page in pages:
        rp=inputs/'raw'/(page['id']+'.json'); mp=inputs/'markdown'/(page['id']+'.md')
        assert rp.is_file() and mp.is_file()
        bindings.append(dict(raw=str(rp),raw_sha256=sha(rp),markdown=str(mp),markdown_sha256=sha(mp),source=page['image'],source_sha256=sha(page['image'])))
        blocks=load(rp)['blocks']
        owners=[(owner,b) for owner,b in enumerate(blocks) if b['type']=='image' and b.get('angle') in [None,0] and not b.get('content')]
        if not owners:continue
        with Image.open(page['image']) as original:
            im=original.convert('RGB')
            for owner,b in owners:
                rect=[round(v*(im.width if i%2==0 else im.height)) for i,v in enumerate(b['bbox'])]
                if rect[0]<0 or rect[1]<0 or rect[2]>im.width or rect[3]>im.height or rect[2]-rect[0]<84 or rect[3]-rect[1]<84:continue
                crop=im.crop(rect); f=features(crop)
                relation=relation_features(crop,f) if f['eligible'] else dict(eligible=False,reason='base_geometry_rejected')
                records.append(dict(ordinal=len(records),page=page['id'],owner=owner,source=page['image'],source_sha256=bindings[-1]['source_sha256'],raw=str(rp),raw_sha256=bindings[-1]['raw_sha256'],bbox=b['bbox'],rect=rect,features=f,relation=relation))
    plan=[request(c,c['rect'],'[layout]') for c in records if c['relation']['eligible']]
    save(out/'census.json',dict(pages=len(pages),records=records,input_bindings=bindings,base_eligible=sum(c['features']['eligible'] for c in records),eligible_owners=len(plan),eligible_pages=len({c['page'] for c in records if c['relation']['eligible']}),HTTP=0,GT_hidden=True,wall_seconds=time.monotonic()-start))
    save(out/'layout_plan.json',dict(requests=plan))
    create(out/'dependencies.json',ENTRIES)
    binding=dict(out=str(out),inputs=cfg['inputs'],inputs_sha256=input_digest(inputs),manifest=str(out/'input_manifest.json'),manifest_sha256=sha(out/'input_manifest.json'),source_hashes={p['image']:sha(p['image']) for p in pages},census_sha256=sha(out/'census.json'),layout_plan_sha256=sha(out/'layout_plan.json'),gpus=cfg['gpus'],caps=cfg['caps'],maximum_HTTP=cfg['caps']['total'],retry=0)
    save(out/'admission_binding.json',binding)
    save(out/'budget.json',dict(caps=cfg['caps'],reserved=0,identities=[],by_stage={},by_source={},by_owner={},owner_layout={},attempts=[],denials=[]))
    save(out/'preflight.json',dict(status='PASS',scope='input source/dependency binding and GT-hidden pure census; not quality validation',HTTP=0))
    print(json.dumps(dict(pages=len(pages),eligible_owners=len(plan),eligible_pages=load(out/'census.json')['eligible_pages'],wall_seconds=time.monotonic()-start)))

def formula_plan(out):
    records=load(out/'census.json')['records'];observations=[]
    for p in sorted(out.glob('gpu*_layout/results.json')):observations+=load(p)
    save(out/'layout_observations.json',observations)
    req=[];decisions=[]
    for r in sorted(observations,key=lambda x:x['ordinal']):
        c=records[r['ordinal']]
        if not valid_record(r) or not r.get('finished_normally'):
            decisions.append(dict(ordinal=c['ordinal'],reason='invalid_layout',selected=False));continue
        with Image.open(c['source']) as original:
            im=original.convert('RGB')
            for i,leaf in enumerate(helper().parse_layout_output(r['raw_answer'])):
                rect,why=gate(im,c['rect'],leaf,load(c['raw'])['blocks'],c['owner'])
                decisions.append(dict(ordinal=c['ordinal'],leaf_index=i,selected=rect is not None,**why))
                if rect is not None:req.append(request(c,rect,'equation',leaf_index=i,source_gate=why,layout_observations_sha256=sha(out/'layout_observations.json')))
    save(out/'formula_plan.json',dict(requests=req,gate_decisions=decisions))

def run(a,out):
    import fcntl
    runlock=(out/'driver.lock').open('a+')
    fcntl.flock(runlock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    admitted(out,a.final_permit,a.final_permit_sha256)
    assert not list(out.glob('protocol_failure_*.json')), 'Fatal queue cannot resume without new reviewed version/run'
    cfg=load(out/'runtime_inputs.json')
    # Serialized stages; GPU lanes run independently within each stage.
    for stage in ['layout','formula']:
        if stage=='formula':formula_plan(out)
        workers=[]
        for lane,gpu in enumerate(cfg['gpus']):
            argv=[sys.executable,'-B',str(ROOT/'code/experimenter/sparse_image_0122_worker_v6.py'),'--out',str(out),'--stage',stage,'--plan',stage+'_plan.json','--gpu',str(gpu),'--lane-index',str(lane),'--lane-count',str(len(cfg['gpus']))]
            if a.final_permit:argv+=['--final-permit',a.final_permit,'--final-permit-sha256',a.final_permit_sha256]
            stream=(out/f'{stage}_gpu{gpu}.log').open('a');workers.append((subprocess.Popen(argv,stdout=stream,stderr=subprocess.STDOUT),stream))
        codes=[]
        for worker,stream in workers:codes.append(worker.wait());stream.close()
        assert not any(codes), 'Worker failed; durable attempts retained; rerun resumes without retries'
    verify_run(out)

def normalized_math(answer):
    if any(s in answer for s in ['<|','<table','\\begin']):return None
    content=helper().post_process([ContentBlock(type='equation',bbox=[0,0,1,1],angle=0,content=answer)])[0].content.strip()
    m=re.fullmatch(r'\\\[(.*?)\\\]',content,re.S)
    if not m or any(s in content for s in ['<|','<table','\\begin']):return None
    depth=0
    for ch in m[1]:
        if ch=='{':depth+=1
        if ch=='}':depth-=1
        if depth<0:return None
    return content if depth==0 and any(ch.isalnum() for ch in m[1]) else None

def compose(out):
    check_binding(out); cfg=load(out/'runtime_inputs.json'); source=Path(cfg['inputs'])
    destination=out/'candidate/predictions'; receipt=out/'candidate/composition.json'
    if receipt.exists(): verify_run(out);print('ALREADY_COMPOSED');return
    assert not destination.exists(), 'Partial compose retained; never overwrite'
    records=load(out/'census.json')['records']; layouts={r['ordinal']:r for r in load(out/'layout_observations.json')}
    responses=sum([load(p) for p in sorted(out.glob('gpu*_formula/results.json'))],[])
    edits=collections.defaultdict(list); decisions=[];seen=set()
    for r in responses:
        c=records[r['ordinal']]; d=dict(ordinal=c['ordinal'],leaf_index=r.get('leaf_index'),identity_key=r['identity_key'],configured=True,triggered=True,applied=False,consumed=r.get('consumed',False),selected=False,scored=False,reason='invalid_observation');decisions.append(d)
        if not valid_record(r) or not r.get('finished_normally'):continue
        assert r['identity_key'] not in seen;seen.add(r['identity_key'])
        assert sha(out/'layout_observations.json')==r['layout_observations_sha256']
        leaf=helper().parse_layout_output(layouts[c['ordinal']]['raw_answer'])[r['leaf_index']]
        raw=load(c['raw'])
        with Image.open(c['source']) as original:
            im=original.convert('RGB');rect,why=gate(im,c['rect'],leaf,raw['blocks'],c['owner'])
            assert rect==r['rect'] and why==r['source_gate']
            bbox=[v/(im.width if i%2==0 else im.height) for i,v in enumerate(rect)]
        content=normalized_math(r['raw_answer'])
        if content is None:d['reason']='parser_rejected';continue
        md=(source/'markdown'/(c['page']+'.md')).read_bytes()
        anchor=next(((i,b['content']) for i,b in enumerate(raw['blocks']) if i>c['owner'] and len(b.get('content') or '')>5 and md.count(b['content'].encode())==1),None)
        if anchor is None:d['reason']='no_unique_following_native_anchor';continue
        if any(max(0,min(e['rect'][2],rect[2])-max(e['rect'][0],rect[0]))*max(0,min(e['rect'][3],rect[3])-max(e['rect'][1],rect[1]))>0 for e in edits[c['page']]):d['reason']='overlapping_new_leaves';continue
        edits[c['page']].append(dict(owner=c['owner'],leaf_index=r['leaf_index'],ordinal=c['ordinal'],rect=rect,bbox=bbox,content=content,anchor=anchor[1],anchor_index=anchor[0]))
        d.update(selected=True,applied=True,reason='fixed_source_gate_native_postprocess_unique_anchor')
    for sub in ['raw','markdown']:(destination/sub).mkdir(parents=True)
    outputs={};changed=[]
    for p in load(out/'input_manifest.json'):
        name=p['id'];rp=source/'raw'/(name+'.json');mp=source/'markdown'/(name+'.md');rows=edits.get(name,[])
        if rows:
            raw=load(rp);blocks=[]
            for i,b in enumerate(raw['blocks']):
                blocks.append(b)
                for row in sorted((r for r in rows if r['owner']==i),key=lambda r:(r['rect'][1],r['rect'][0])):blocks.append(dict(type='equation',bbox=row['bbox'],angle=0,content=row['content'],source_image_parent_index=i,source_relation='complete_separated_equation_inside_preserved_image'))
            raw['blocks']=blocks;save(destination/'raw'/rp.name,raw)
            original=mp.read_bytes(); groups=collections.defaultdict(list)
            for row in sorted(rows,key=lambda r:(r['owner'],r['rect'][1],r['rect'][0])):groups[row['anchor'].encode()].append(row['content'].encode())
            inserts=sorted([(original.index(anchor),b'\n\n'.join(parts)+b'\n\n') for anchor,parts in groups.items()],reverse=True)
            md=original
            for pos,data in inserts:md=md[:pos]+data+md[pos:]
            (destination/'markdown'/mp.name).write_bytes(md);changed.append(name)
        else:
            os.link(rp.resolve(),destination/'raw'/rp.name);os.link(mp.resolve(),destination/'markdown'/mp.name)
        for sub,path in [('raw',rp),('markdown',mp)]:outputs[f'{sub}/{path.name}']=sha(destination/sub/path.name)
    save(receipt,dict(status='UNADOPTED',pages=len(load(out/'input_manifest.json')),changed_pages=changed,decisions=decisions,edits=dict(edits),outputs=outputs,GT_hidden=True,new_HTTP=0,source_truth='Requires complete changed-source review; parser is syntax only'))
    verify_run(out)

def verify_run(out):
    check_binding(out); b=load(out/'budget.json')
    assert b['reserved']==len(b['identities'])==len(b['attempts']) and b['reserved']<=b['caps']['total']
    for field,cap in [('by_source','source'),('by_owner','owner')]:assert all(n<=b['caps'][cap] for n in b[field].values())
    assert all(n<=b['caps'][stage] for stage,n in b['by_stage'].items())
    results=sum([load(p) for p in out.glob('gpu*/results.json')],[])
    usages=[audit_usage(p,load(p/'results.json') if (p/'results.json').exists() else []) for p in out.glob('gpu*_*') if p.is_dir()]
    receipt=out/'candidate/composition.json'
    if receipt.exists():
        c=load(receipt); dest=out/'candidate/predictions';source=Path(load(out/'runtime_inputs.json')['inputs'])
        assert len(c['outputs'])==2*c['pages']
        for rel,h in c['outputs'].items():
            p=dest/rel;assert p.is_file() and not p.is_symlink() and sha(p)==h
            if p.stem not in c['changed_pages']:assert sha(source/rel)==h
    executions=[load(p).get('status') for p in out.glob('gpu*/execution.json')]
    failed=sum(r.get('status','').startswith('FAILED') for r in results)
    unknown=b['reserved']-sum(u['known_usage_attempts'] for u in usages)
    assert unknown>=0, 'Usage without reserved transport'
    status='FAILED_PROTOCOL' if list(out.glob('protocol_failure_*.json')) else 'FAILED_RUN' if 'FAILED' in executions else 'COMPLETE_WITH_FAILURES' if failed or unknown else 'COMPLETE_WITH_FALLBACKS' if any(r.get('status')!='CONSUMED' for r in results) else 'PASS'
    save(out/'verification.json',dict(status=status,artifact_verification='PASS',execution_states=executions,HTTP_attempts=b['reserved'],stage_attempts=b['by_stage'],failed_records=sum(r.get('status')!='CONSUMED' for r in results),prompt_tokens=sum(u.get('prompt_tokens',0) for u in usages),completion_tokens=sum(u.get('completion_tokens',0) for u in usages),unknown_usage_attempts=b['reserved']-sum(u['known_usage_attempts'] for u in usages),request_wall_seconds=sum(r.get('wall_seconds',0) for r in results),GPU_busy_seconds=None,selected=sum(d['selected'] for d in load(receipt)['decisions']) if receipt.exists() else None,scored=False))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['initialize','census','permit-request','run','compose','verify']);p.add_argument('--out',required=True);p.add_argument('--inputs');p.add_argument('--image-dir');p.add_argument('--gpus',nargs='+',type=int,default=[0,1]);p.add_argument('--cap',type=int,default=48);p.add_argument('--layout-cap',type=int,default=36);p.add_argument('--formula-cap',type=int,default=12);p.add_argument('--source-cap',type=int,default=6);p.add_argument('--owner-cap',type=int,default=3);p.add_argument('--final-permit');p.add_argument('--final-permit-sha256');p.add_argument('--hidden',action='store_true');a=p.parse_args();out=safe_out(a.out)
    if a.command=='initialize':initialize(a,out);return
    if a.command in ['census','run','compose','verify'] and not a.hidden:
        from panel_hidden_0110_v2 import restricted
        prefix=[] if a.command=='run' else ['unshare','--net']
        command=restricted(out,[*prefix,sys.executable,'-B',__file__,*sys.argv[1:],'--hidden']);os.execvp(command[0],command)
    if a.hidden:
        from single_model_selective_v1 import HIDDEN
        assert all(Path(x).stat().st_size==0 for x in HIDDEN)
    if a.command=='census':census(out)
    elif a.command=='run':run(a,out)
    elif a.command=='compose':compose(out)
    elif a.command=='verify':verify_run(out)
    elif a.command=='permit-request':
        check_binding(out);f=load(ROOT/'control/final_validation_plan.json');freeze=(ROOT/f['runtime_freeze']).resolve()
        save(out/'permit_request.json',dict(approved=False,approved_by=None,mode='final_validation',run_binding=load(out/'admission_binding.json'),source_hashes=verify(out/'dependencies.json')['files'],final_plan_sha256=sha(ROOT/'control/final_validation_plan.json'),runtime_freeze=str(freeze),runtime_freeze_sha256=sha(freeze),not_before=f['start_at'],campaign_deadline=load(ROOT/'control/phase2_plan.json')['deadline_at'],phase=load(ROOT/'control/phase2_plan.json')['phase']))
if __name__=='__main__':main()
