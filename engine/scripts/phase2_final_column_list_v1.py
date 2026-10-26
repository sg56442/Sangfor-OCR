"""Bound fresh narrow-column recovery, followed by source-driven zero-call ordering."""
import hashlib,io,json,os,sys,time,collections
from pathlib import Path
from PIL import Image
from phase2_final_runtime_v1 import ROOT,PYTHON,inside,load,save,sha,verify_hashes
sys.path[:0]=[str(ROOT/'code/research'),str(ROOT/'code/experimenter')]
from column_view_0059 import measure
from column_edits_0063 import assemble,complete
from spacing_state_0044 import audit_rows,costs
from finite_request_identity_0101_v1 import helper,params,prompts,pix,key
from table_transport_preflight_0038_v2 import audit_consumed
from mineru_vl_utils.structs import ContentBlock
from verify_phase2_zero_call_tails_v2 import verify_tail
RUNNER='code/research/column_runtime_0063.py'
LIST_RUNNER='code/research/list_apply_cli_0060.py'

def prepare_column(plan,frozen):
    out=inside(plan['output']);folder=inside(plan['column_output']);assert not folder.exists()
    return [PYTHON,'-B',RUNNER,'prepare','--inputs',out/'B_before_column/predictions','--pages',inside(frozen['pages']),
        '--out',folder,'--gpu',plan['column_gpu'],'--budget',frozen['column_budget'],
        '--native-inputs',out/'native/predictions','--native-audit',out/'native/audit/http.jsonl','--lane-plan',inside(plan['_plan_path'])]

def approve_column(plan,frozen):
    from column_admission_0063 import request
    folder=inside(plan['column_output']);cfg=load(folder/'inputs.json');out=inside(plan['output'])
    assert cfg['model']==frozen['model'] and cfg['gpu']==plan['column_gpu']==plan['gpu'] and cfg['budget']==frozen['column_budget']==8
    for k,p in [('inputs',out/'B_before_column/predictions'),('native_inputs',out/'native/predictions'),('native_audit',out/'native/audit/http.jsonl'),('manifest',inside(frozen['pages']))]:assert Path(cfg[k])==p
    deps=load(folder/'dependencies.json');verify_hashes(deps);assert all(frozen['source_hashes'].get(p)==h for p,h in deps.items())
    permit=request(folder);assert permit['runtime_freeze_sha256']==plan['freeze_sha256'] and permit['run_binding']['weight_sha256']==frozen['weight_sha256']
    permit.update(approved=True,approved_by='RSI');path=folder/'final_permit.json';assert not path.exists();save(path,permit)
    return [PYTHON,'-B',RUNNER,'observe','--out',folder,'--final-permit',path,'--final-permit-sha',sha(path)]

def materialize(folder,target):
    folder,target=map(Path,[folder,target]);assert not target.exists()
    for sub in ['raw','markdown']:
        dest=target/'predictions'/sub;dest.mkdir(parents=True)
        for p in (folder/sub).iterdir():assert p.is_file() and not p.is_symlink();os.link(p,dest/p.name)
    save(target/'receipt.json',dict(kind='verified_column_or_list_materialization',source=str(folder),new_HTTP=0))

def verify_column(folder,source,native,pages,*,frozen=None,plan=None,observation=None):
    began=time.monotonic();folder,source,native,pages=map(lambda p:Path(p).resolve(),[folder,source,native,pages])
    historical=observation is not None;assert not historical or (frozen is None and plan is None)
    observed=Path(observation).resolve() if historical else folder;cfg=load(folder/'inputs.json')
    for k,p in [('inputs',source),('native_inputs',native/'predictions'),('native_audit',native/'audit/http.jsonl'),('manifest',pages)]:assert Path(cfg[k])==p
    assert cfg['model']==params('text')['model'] and cfg['budget']==8 and cfg['gpu'] in ['0','1','3']
    for name in ['dependencies','input_binding','code_lock']:verify_hashes(load(folder/(name+'.json')))
    if frozen is not None:
        assert plan is not None and not historical and cfg['gpu']==plan['column_gpu']==plan['gpu'] and frozen['column_budget']==8
        assert all(frozen['source_hashes'].get(p)==h for p,h in load(folder/'dependencies.json').items())
        from column_admission_0063 import request
        expected=request(folder);expected.update(approved=True,approved_by='RSI');assert expected==load(folder/'final_permit.json')
    manifest=load(pages);assert len(manifest)==1651;binding=load(folder/'input_binding.json');rows=[]
    for page in manifest:
        rp=source/'raw'/(page['id']+'.json');mp=source/'markdown'/(page['id']+'.md')
        for p in [rp,mp,Path(page['image'])]:assert binding[str(p)]==sha(p)
        raw=load(rp);im=None
        for i,b in enumerate(raw['blocks']):
            if b.get('type')!='table':continue
            bb=b['bbox'];ww=bb[2]-bb[0];hh=bb[3]-bb[1]
            if ww<=0 or hh<=0 or hh<.3 or ww>.12:continue
            if im is None:im=Image.open(page['image']).convert('RGB')
            m=measure(im,b)
            if m is None:continue
            priority=hashlib.sha256(json.dumps(dict(content=b.get('content'),bbox=bb),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            rows.append(dict(source=page['image'],source_sha256=sha(page['image']),raw=str(rp),raw_sha256=sha(rp),owner=i,priority=priority,geometry=m))
        if im is not None:im.close()
    rows.sort(key=lambda r:r['priority']);census=load(folder/'census.json');assert rows==census['rows'] and census['pages']==1651
    qs=load(folder/'processor_plan.json');risks=[r for r in rows if r['geometry']['risk']][:8];assert len(qs)==len(risks)
    ledger=load(folder/'ledger.json');assert not ledger.get('protocol_fatal')
    if historical:assert ledger==load(observed/'ledger.json')
    audits=audit_rows(observed/'audit/http.jsonl');cf={r['request_sha256']:r for r in audits if r['stage']=='configured'};cu={r['request_sha256']:r for r in audits if r['stage']=='consumed'}
    native_rows=audit_rows(native/'audit/http.jsonl');nc={r['request_sha256']:r for r in native_rows if r['stage']=='configured'};nu={r['request_sha256']:r for r in native_rows if r['stage']=='consumed'}
    used=[r for r in ledger['records'].values() if r['status']!='NOT_ADMITTED'];assert len(used)<=8
    assert max(collections.Counter(r['owner'] for r in used).values(),default=0)<=1
    assert max(collections.Counter(r['owner'].split(':')[0] for r in used).values(),default=0)<=4
    if used:
        svc=load(observed/'service.json');assert svc['model']==cfg['model'] and svc['read_only_checkpoint_mount']
        assert svc['weight_sha256']=='01dcb5addfa1d6133fd0930e79fa2484817cb0228af21cb4917fa73d04fa3147';verify_hashes(svc['processor_hashes'])
        if frozen is not None:assert svc['container_id']==frozen['services'][cfg['gpu']]['container_id']
    processor=None
    if qs:
        import torch
        from transformers import AutoProcessor
        torch.set_num_threads(2);processor=AutoProcessor.from_pretrained(cfg['model'],local_files_only=True)
    def measured(im,prompt):
        msg=[dict(role='system',content='You are a helpful assistant.'),dict(role='user',content=[dict(type='image',image=im),dict(type='text',text=prompt)])]
        value=processor(text=[processor.apply_chat_template(msg,tokenize=False,add_generation_prompt=True)],images=[im],return_tensors='pt')
        return dict(prompt_tokens=int(value['input_ids'].shape[-1]),tensor_sha256=hashlib.sha256(value['pixel_values'].numpy().tobytes()).hexdigest(),grid=value['image_grid_thw'].tolist())
    pending={};selected=[];expected_keys=set()
    for q,risk in zip(qs,risks):
        for k,v in risk.items():assert q[k]==v
        assert len(q['tasks'])==1;t=q['tasks'][0]
        for ref,kind in [('native_receipt','text'),('original_owner_native_receipt','table')]:
            record=q[ref];k=record['request_sha256'];assert record==dict(nc[k],consumed=nu[k])
            assert record['parameters']==params(kind) and record['prompts']==prompts(kind)
            response=record['consumed']['response'];assert response['model']==cfg['model'] and len(response['choices'])==1 and response['choices'][0]['finish_reason']=='stop'
        raw=load(q['raw']);block=raw['blocks'][q['owner']]
        with Image.open(q['source']) as im:
            im=im.convert('RGB');w,h=im.size;geo=measure(im,block)
            data,prompt,_,_=helper().prepare_for_extract(im.crop(geo['expanded_box']),[ContentBlock(type='text',bbox=[0,0,1,1],angle=0)])
            nd,_,_,_=helper().prepare_for_extract(im,[ContentBlock(type='table',bbox=block['bbox'],angle=0)])
        assert data[0]==(folder/f'view_{q["index"]}_0.bin').read_bytes() and hashlib.sha256(data[0]).hexdigest()==t['encoded_sha256']
        pim=Image.open(io.BytesIO(data[0])).convert('RGB');nim=Image.open(io.BytesIO(nd[0])).convert('RGB')
        assert pix(pim)==t['pixel_sha256'] and pix(nim)==q['native_pixel_sha256'] and t['identity']==key(pim.size,pix(pim),'text')
        assert t['parameters']==params('text') and t['prompt']==prompt[0]==prompts('text')[0]['text']
        assert t['processor']==measured(pim,t['prompt']) and q['native_processor']==measured(nim,t['prompt'])
        identity=hashlib.sha256(json.dumps(dict(pixel=t['pixel_sha256'],prompt=t['prompt'],parameters=t['parameters']),sort_keys=True).encode()).hexdigest();expected_keys.add(identity)
        z=ledger['records'].get(identity);assert z is not None
        if z.get('request_sha256') in cu:
            k=z['request_sha256'];audit_consumed(cf[k],cu[k],t,params('text'));assert cu[k]['response']['model']==cfg['model']
            if z.get('response'):assert z['response']==cu[k]['response']
            assert cu[k]['response']['usage']['prompt_tokens']==t['processor']['prompt_tokens']
        text=complete([z])
        if text is None:continue
        bbox=[v/s for v,s in zip(geo['expanded_box'],[w,h,w,h])]
        overlap=[i for i,b in enumerate(raw['blocks']) if i!=q['owner'] and b.get('content') and b.get('bbox') and max(0,min(b['bbox'][2],bbox[2])-max(b['bbox'][0],bbox[0]))*max(0,min(b['bbox'][3],bbox[3])-max(b['bbox'][1],bbox[1]))>0]
        if geo['risk'] and not overlap and text.strip() and '<table' not in text:
            stem=Path(q['raw']).stem;pending.setdefault(stem,[]).append((q['owner'],dict(block,type='text',content=text,bbox=bbox)));selected.append((stem,q['owner']))
    assert set(ledger['records'])==expected_keys
    changed=[]
    for page in manifest:
        stem=page['id'];rp=source/'raw'/(stem+'.json');mp=source/'markdown'/(stem+'.md');rb,md=rp.read_bytes(),mp.read_bytes()
        nr,nm,_=assemble(rb,md,pending[stem]) if stem in pending else (rb,md,None)
        for sub,p,data in [('raw',rp,nr),('markdown',mp,nm)]:assert (folder/'selected_predictions'/sub/p.name).read_bytes()==data
        if (rb,md)!=(nr,nm):changed.append(stem)
    assert all(len(list((folder/'selected_predictions'/sub).iterdir()))==1651 for sub in ['raw','markdown'])
    cost=costs(ledger,observed/'audit/http.jsonl');assert cost==load(observed/'cost.json') and not cost['orphan_consumed_requests']
    result=dict(actual_attempts=cost['durable_attempts'],extra_prompt_tokens=cost['known_prompt_tokens'],extra_completion_tokens=cost['known_completion_tokens'],
        failed=sum(r['status']!='COMPLETE' for r in used),unknown_usage=cost['claims_without_consumed_response']+cost['unknown_usage_responses'],
        wall_seconds=cost['known_invocation_wall_seconds'],prepare_seconds=load(folder/'prepare_timing.json')['seconds'],
        selected_pages=len(changed),selected_owners=len(selected),risk_owners=census['risk'],ledger_costs=cost)
    return result,time.monotonic()-began
