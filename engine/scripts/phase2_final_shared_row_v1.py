"""Fresh shared top-row observation and exact, source-bound ownership transfer."""
import hashlib, io, json, os, sys, time
from pathlib import Path
from PIL import Image
from phase2_final_runtime_v1 import ROOT,PYTHON,inside,load,save,sha,verify_hashes
sys.path[:0]=[str(ROOT/'code/research'),str(ROOT/'code/experimenter'),str(ROOT/'code/runtime')]
from phase2_final_numeric_mode_v1 import identity
from spacing_state_0044 import audit_rows,costs
from spacing_apply_0046 import span
from shared_header_0056 import geometry,select
from boundary_view_0055 import detect,expand
from phase2_mixed_prose_runtime_v1 import owner_tokens
from repeated_runtime_0048b import patch
from finite_request_identity_0101_v1 import helper,pix,params,prompts,key
from table_transport_preflight_0038_v2 import audit_consumed
from mineru_vl_utils.post_process import simple_process
from mineru_vl_utils.structs import ContentBlock

RUNNER='code/research/shared_header_runtime_0058.py'
MANIFEST='reports/researcher_phase2_0044/runtime/dependencies.json'

def prepare_shared_row(plan,frozen):
    out=inside(plan['output']);folder=inside(plan['shared_row_output'])
    assert folder.parent==ROOT/'runs' and not folder.exists()
    assert frozen['source_hashes'][str(ROOT/MANIFEST)]==sha(ROOT/MANIFEST)
    return [PYTHON,'-B',RUNNER,'prepare','--out',folder,'--inputs',out/'B_before_shared_row/predictions',
        '--pages',inside(frozen['pages']),'--native-inputs',out/'native/predictions',
        '--native-audit',out/'native/audit/http.jsonl','--gpu',plan['shared_row_gpu'],
        '--budget',str(frozen['shared_row_budget']),'--lane-plan',inside(plan['_plan_path'])]

def approve_shared_row(plan,frozen):
    from shared_header_admission_0058 import request
    folder=inside(plan['shared_row_output']);cfg=load(folder/'inputs.json');out=inside(plan['output'])
    assert cfg['model']==frozen['model'] and cfg['gpu']==plan['shared_row_gpu']==plan['gpu']
    assert cfg['budget']==frozen['shared_row_budget']==8
    for k,p in [('inputs',out/'B_before_shared_row/predictions'),('native_inputs',out/'native/predictions'),
                ('native_audit',out/'native/audit/http.jsonl'),('manifest',inside(frozen['pages']))]: assert Path(cfg[k])==p
    deps=load(folder/'dependencies.json');verify_hashes(deps)
    assert all(frozen['source_hashes'].get(p)==h for p,h in deps.items())
    permit=request(folder);assert permit['runtime_freeze_sha256']==plan['freeze_sha256']
    assert permit['run_binding']['weight_sha256']==frozen['weight_sha256']
    permit.update(approved=True,approved_by='RSI');path=folder/'final_permit.json';assert not path.exists();save(path,permit)
    return [PYTHON,'-B',RUNNER,'observe','--out',folder,'--final-permit',path,'--final-permit-sha',sha(path)]

def verify_shared_row(folder,source,native,pages,*,frozen=None,plan=None,observation=None,bridge=None):
    began=time.monotonic();folder,source,native,pages=map(lambda p:Path(p).resolve(),[folder,source,native,pages])
    historical=observation is not None
    assert not historical or (frozen is None and plan is None and bridge is None)
    observed=Path(observation).resolve() if historical else folder
    cfg=load(folder/'inputs.json')
    assert Path(cfg['inputs'])==source and Path(cfg['manifest'])==pages
    assert Path(cfg['native_inputs'])==native/'predictions' and Path(cfg['native_audit'])==native/'audit/http.jsonl'
    assert cfg['model']==params('table')['model'] and cfg['budget']==8 and cfg['gpu'] in ['0','1','3']
    for name in ['dependencies','input_binding','code_lock','census_input_binding']:verify_hashes(load(folder/(name+'.json')))
    if frozen is not None:
        assert plan is not None and not historical
        assert cfg['gpu']==plan['shared_row_gpu']==plan['gpu'] and cfg['budget']==frozen['shared_row_budget']
        assert all(frozen['source_hashes'].get(p)==h for p,h in load(folder/'dependencies.json').items())
        assert frozen['source_hashes'][str(ROOT/MANIFEST)]==sha(ROOT/MANIFEST)
        from shared_header_admission_0058 import request
        expected=request(folder);expected.update(approved=True,approved_by='RSI')
        assert expected==load(folder/'final_permit.json')
    manifest=load(pages);by_id={q['id']:q for q in manifest};assert len(by_id)==len(manifest)==1651
    binding={str(source/'raw'/(name+'.json')):sha(source/'raw'/(name+'.json')) for name in by_id}
    assert binding==load(folder/'census_input_binding.json')
    census=load(folder/'census.json');assert census['pages']==1651 and census['HTTP']==0
    assert census['input_binding_sha256']==hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest()
    risks=[q for q in census['rows'] if q['input_risk']]
    assert census['rows']==sorted(census['rows'],key=lambda q:q['priority'])
    assert census['risk_owners']==len(risks) and census['risk_sources']==len({q['source'] for q in risks})
    prepared=load(folder/'processor_plan.json');assert len(prepared)==len(risks[:cfg['budget']])
    ledger=load(folder/'ledger.json');assert not ledger.get('protocol_fatal')
    tasks={identity(t):(q,t) for q in prepared for t in q['tasks']}
    assert len(tasks)==len(prepared) and tasks.keys()==ledger['records'].keys()
    configured={};consumed={}
    for row in audit_rows(observed/'audit/http.jsonl'):
        if row['stage'] in ['configured','consumed']:
            dest=configured if row['stage']=='configured' else consumed
            assert row['request_sha256'] not in dest;dest[row['request_sha256']]=row
    need={q['native_pixel_sha256'] for q in prepared};native_config={};native_wire={}
    for row in audit_rows(native/'audit/http.jsonl'):
        if row['stage']=='configured':
            for im in row.get('images',[]):
                if im['pixel_sha256'] in need:native_config[row['request_sha256']]=dict(pixel=im['pixel_sha256'],parameters=row['parameters'],prompts=row['prompts'])
        elif row['stage']=='consumed' and row['request_sha256'] in native_config:
            v=native_config[row['request_sha256']];native_wire[v['pixel']]=dict(request_sha256=row['request_sha256'],**v)
    claims=[r for r in ledger['records'].values() if r['status']!='NOT_ADMITTED']
    assert len(claims)<=cfg['budget'] and len({r['owner'] for r in claims})==len(claims)
    for h in {r['owner'].split(':')[0] for r in claims}:assert sum(r['owner'].split(':')[0]==h for r in claims)<=4
    if claims:
        svc=load(observed/'service.json');assert svc['read_only_checkpoint_mount'] and svc['model']==cfg['model']
        assert svc['weight_sha256']=='01dcb5addfa1d6133fd0930e79fa2484817cb0228af21cb4917fa73d04fa3147';verify_hashes(svc['processor_hashes'])
        if frozen is not None:assert svc['container_id']==frozen['services'][cfg['gpu']]['container_id']
    configured_keys={}
    for request,cf in configured.items():
        matches=[k for k,(q,t) in tasks.items() if len(cf['images'])==1 and cf['images'][0]['pixel_sha256']==t['pixel_sha256'] and cf['parameters']==t['parameters'] and cf['prompts']==prompts('table')]
        assert len(matches)==1 and matches[0] not in configured_keys;k=matches[0];configured_keys[k]=request
        assert ledger['records'][k]['status']!='NOT_ADMITTED'
        if request in consumed:
            q,t=tasks[k];audit_consumed(cf,consumed[request],t,params('table'));assert consumed[request]['response']['model']==cfg['model']
    assert consumed.keys()<=configured.keys()
    import torch
    from transformers import AutoProcessor
    torch.set_num_threads(2);processor=AutoProcessor.from_pretrained(cfg['model'],local_files_only=True)
    def measure(im,prompt):
        msg=[dict(role='system',content='You are a helpful assistant.'),dict(role='user',content=[dict(type='image',image=im),dict(type='text',text=prompt)])]
        v=processor(text=[processor.apply_chat_template(msg,tokenize=False,add_generation_prompt=True)],images=[im],return_tensors='pt')
        return dict(prompt_tokens=int(v['input_ids'].shape[-1]),tensor_sha256=hashlib.sha256(v['pixel_values'].numpy().tobytes()).hexdigest(),grid=v['image_grid_thw'].tolist())
    pending={};selected=[]
    for q,seed in zip(prepared,risks[:cfg['budget']]):
        assert all(q[k]==v for k,v in seed.items() if k!='geometry')
        assert q['raw_sha256']==sha(q['raw']) and q['source_sha256']==sha(q['source'])
        assert q['source']==by_id[Path(q['raw']).stem]['image']
        assert len(q['tasks'])==1;t=q['tasks'][0];ident=identity(t);rec=ledger['records'][ident]
        raw=load(q['raw']);owner=raw['blocks'][q['owner']];old=owner['content']
        nb=load(native/'predictions/raw'/Path(q['raw']).name)['blocks'][q['owner']]
        assert all(owner[k]==nb[k] for k in ['type','bbox','angle'])
        with Image.open(q['source']) as im:
            im=im.convert('RGB');a,box,hits=detect(im,owner['bbox']);_,expanded=expand(a,box,hits)
            assert expanded==q['expanded']==q['geometry'] and any('top' in z['sides'] for z in hits)
            assert geometry(im,owner,raw['blocks'][q['caption_owner']],expanded)==seed['geometry']
            data,prompt,_,_=helper().prepare_for_extract(im.crop(expanded['expanded_box']),[ContentBlock(type='table',bbox=[0,0,1,1],angle=0)])
            nd,_,_,_=helper().prepare_for_extract(im,[ContentBlock(type='table',bbox=owner['bbox'],angle=owner.get('angle',0))])
        assert data[0]==(folder/f'view_{q["index"]}_0.bin').read_bytes() and sha(folder/f'view_{q["index"]}_0.bin')==t['encoded_sha256']
        pim=Image.open(io.BytesIO(data[0])).convert('RGB');nim=Image.open(io.BytesIO(nd[0])).convert('RGB')
        assert pix(pim)==t['pixel_sha256'] and t['identity']==key(pim.size,pix(pim),'table')
        assert pix(nim)==q['native_pixel_sha256'] and q['native_receipt']==native_wire[pix(nim)]
        assert t['prompt']==prompt[0]==prompts('table')[0]['text'] and t['parameters']==q['native_receipt']['parameters']==params('table')
        assert q['native_processor']==measure(nim,t['prompt']) and t['processor']==measure(pim,t['prompt'])
        assert t['processor']['prompt_tokens']+4096<=8192 and t['processor']['tensor_sha256']!=q['native_processor']['tensor_sha256']
        assert rec['owner']==q['source_sha256']+':'+str(q['owner'])
        if rec['status']!='COMPLETE':
            if rec['status']=='NOT_ADMITTED':assert ident not in configured_keys
            continue
        req=configured_keys[ident];rs=consumed[req]['response']
        assert rec['request_sha256']==req and rec['response']==rs and rs['choices'][0]['finish_reason']=='stop'
        assert rec['text']==rs['choices'][0]['message']['content'] and rs['usage']['prompt_tokens']==t['processor']['prompt_tokens']
        new=simple_process([ContentBlock(type='table',bbox=[0,0,1,1],content=rec['text'])])[0].content
        with Image.open(q['source']) as im:d=select(im,old,new,raw['blocks'],q['owner'],q['geometry'])
        if not d['accepted']:continue
        rp=Path(q['raw']);rb=rp.read_bytes();md=(source/'markdown'/(rp.stem+'.md')).read_bytes()
        try:
            rm=owner_tokens(rb,raw);caption=d['caption_owner'];re=[(*rm[(q['owner'],'content')],json.dumps(new,ensure_ascii=False).encode()),(*rm[(caption,'content')],b'null')]
            me=[span(md,old,new),span(md,raw['blocks'][caption]['content'],'')]
            prior=pending.get(rp.stem,dict(rb=rb,md=md,re=[],me=[]))
            for changes,previous in [(re,prior['re']),(me,prior['me'])]:
                ordered=sorted(previous+changes);assert all(a[1]<=b[0] for a,b in zip(ordered,ordered[1:]))
        except (AssertionError,KeyError,ValueError):continue
        pending[rp.stem]=prior;prior['re']+=re;prior['me']+=me;selected.append(dict(page=rp.stem,owner=q['owner'],decision=d))
    candidate=folder/'selected_predictions'
    for sub in ['raw','markdown']:
        assert len(list((candidate/sub).iterdir()))==1651
        for name in by_id:
            p=source/sub/(name+('.json' if sub=='raw' else '.md'));dest=candidate/sub/p.name
            expected=p.read_bytes()
            if name in pending:
                item=pending[name];expected=patch(item['rb' if sub=='raw' else 'md'],item['re' if sub=='raw' else 'me'])
            assert dest.is_file() and not dest.is_symlink() and dest.read_bytes()==expected
            if bridge is not None:assert (Path(bridge)/'predictions'/sub/p.name).read_bytes()==expected
    cost=costs(ledger,observed/'audit/http.jsonl');assert cost==load(observed/'cost.json')
    return dict(actual_attempts=len(claims),attempts_are_conservative_upper_bound=True,configured_HTTP=len(configured),consumed_HTTP=len(consumed),
        extra_prompt_tokens=cost['known_prompt_tokens'],extra_completion_tokens=cost['known_completion_tokens'],
        unknown_usage_attempts=len(cost['unknown_attempt_usage']),unknown_usage_responses=cost['unknown_usage_responses'],
        failed=sum(r['status']!='COMPLETE' for r in claims),wall_seconds=cost['known_invocation_wall_seconds'],
        prepare_seconds=load(folder/'prepare_timing.json')['seconds'],risk_owners=census['risk_owners'],risk_sources=census['risk_sources'],
        selected_pages=len(pending),selected_owners=len(selected),selected=selected,ledger_costs=cost),time.monotonic()-began

def materialize_shared_row(folder,target):
    folder,target=map(Path,[folder,target]);assert not target.exists()
    for sub in ['raw','markdown']:
        dest=target/'predictions'/sub;dest.mkdir(parents=True)
        for p in (folder/'selected_predictions'/sub).iterdir():assert p.is_file() and not p.is_symlink();os.link(p,dest/p.name)
    save(target/'receipt.json',dict(kind='fresh_shared_row_verified_materialization',source=str(folder),new_HTTP=0))
