"""Fresh same-MinerU brace admission, full input binding and exact byte reconstruction."""
import base64,hashlib,io,json,os,sys,time
from pathlib import Path
from PIL import Image
from phase2_final_runtime_v1 import ROOT,PYTHON,inside,load,save,sha,now,verify_hashes
sys.path[:0]=[str(ROOT/'code/experimenter'),str(ROOT/'code/runtime')]
from brace_production_0136_v5 import gate,anchor
from brace_compose_0136_v4 import spans,select
from finite_request_identity_0101_v1 import params,prompts,pix,key,helper
from mineru_vl_utils.structs import ContentBlock

RUNNER='scripts/phase2_brace_fresh_runtime_v1.py'
TRANSPORT='code/experimenter/brace_transport_0136_v3.py'
TIME_GATE='code/experimenter/phase2_final_time_gate_v1.py'

def binding(source,pages,folder,gpu,budget):
    source,pages,folder=map(lambda p:Path(p).resolve(),[source,pages,folder])
    images={p.stem:p for p in pages.iterdir() if p.is_file()}
    files=sorted((source/'raw').glob('*.json'));assert len(files)==1651
    fingerprints=[(p.name,sha(p),sha(source/'markdown'/(p.stem+'.md')),sha(images[p.stem])) for p in files]
    return dict(kind='brace_current_input',input_tree_sha256=hashlib.sha256(json.dumps(fingerprints).encode()).hexdigest(),
        inputs=str(source),pages=str(pages),out=str(folder),gpu=str(gpu),budget=budget)

def image_directory(pages):
    manifest=load(pages);assert len(manifest)==len({p['id'] for p in manifest})==1651
    parents={str(Path(p['image']).parent) for p in manifest};assert len(parents)==1
    return Path(parents.pop())

def prepare_brace(plan,frozen):
    folder=inside(plan['brace_output']);source=inside(plan['output'])/'B_before_brace/predictions'
    assert folder.parent==ROOT/'runs' and not folder.exists()
    pages=image_directory(inside(frozen['pages']));gpu=plan['brace_gpu'];budget=frozen['brace_budget']
    assert gpu==plan['gpu'] and 0<=budget<=8
    deps=load(inside(frozen['brace_dependencies']))['files'];verify_hashes(deps)
    assert all(frozen['source_hashes'].get(p)==h for p,h in deps.items())
    hashes=dict(deps)
    for name in [RUNNER,TRANSPORT,TIME_GATE,'scripts/phase2_final_brace_v1.py']:
        hashes[str(ROOT/name)]=sha(ROOT/name);assert frozen['source_hashes'][str(ROOT/name)]==sha(ROOT/name)
    control=load(ROOT/'control/final_validation_plan.json')
    permit=dict(mode='final_validation',approved=True,approved_by='RSI',phase=control['phase'],
        run_binding=binding(source,pages,folder,gpu,budget),source_hashes=hashes,dependency_hashes=deps,
        campaign_deadline=control['deadline_at'],not_before=control['start_at'],
        runtime_freeze_sha256=plan['freeze_sha256'])
    path=inside(plan['output'])/'brace_final_permit.json';assert not path.exists();save(path,permit)
    return [PYTHON,'-B',RUNNER,'--inputs',source,'--pages',pages,'--out',folder,'--gpu',gpu,'--budget',str(budget),
        '--final-validation-admission',path,'--final-validation-sha256',sha(path)]

def reconstruct(raw_bytes,md_bytes,qs,responses):
    s=raw_bytes.decode();md=md_bytes.decode();raw=json.loads(s);blocks=raw['blocks'];ri=[];mi=[];decisions=[]
    try:positions=spans(s)
    except (AssertionError,KeyError,ValueError,IndexError):return raw_bytes,md_bytes,0
    for q in sorted(qs,key=lambda x:x['owner']):
        a=responses.get(q['ordinal'],{});text=a.get('text','');i=q['owner'];accept,_=select(text,a.get('finish'),blocks,i)
        at=anchor(blocks,i,md)
        if not (a.get('finish')=='stop' and text.strip() and accept and at is not None):continue
        nl='\r\n' if '\r\n' in md else '\n';text_md=text.replace('\r\n','\n').replace('\n',nl)
        b=dict(type='text',bbox=blocks[i]['bbox'],angle=0,content=text,merge_prev=False)
        ri.append((positions[i][1],','+json.dumps(b,ensure_ascii=False)));mi.append((at,text_md+nl+nl));decisions.append(i)
    def splice(old,edits):
        out=old
        for _,(at,text) in sorted(enumerate(edits),key=lambda x:(x[1][0],x[0]),reverse=True):out=out[:at]+text+out[at:]
        return out.encode()
    return splice(s,ri),splice(md,mi),len(decisions)

def verify_brace(folder,source,pages,*,plan=None,frozen=None,observation=None,research_predictions=None,bridge=None):
    """observation is research-only proof reuse; final mode requires fresh local wire."""
    folder,source,pages=map(lambda p:Path(p).resolve(),[folder,source,pages]);began=time.monotonic()
    historical=observation is not None
    assert not historical or (plan is None and frozen is None and bridge is None and research_predictions is not None)
    assert historical or research_predictions is None
    observation=Path(observation).resolve() if historical else folder
    census=load(folder/'plan.json');prepared=load(folder/'prepared.json');responses=load(observation/'responses.json')
    assert load(folder/'runtime_inputs.json')['inputs']==str(source)
    deps=load(folder/'dependencies.json')['files'];verify_hashes(deps)
    images=image_directory(pages);expected_binding=binding(source,images,folder,census['gpu'],census['budget'])
    if frozen is not None:
        assert plan is not None and not historical
        assert all(frozen['source_hashes'].get(p)==h for p,h in deps.items())
        assert census['gpu']==plan['brace_gpu']==plan['gpu'] and census['budget']==frozen['brace_budget']
        assert deps==load(inside(frozen['brace_dependencies']))['files']
        permit=load(inside(plan['output'])/'brace_final_permit.json')
        assert permit['run_binding']==expected_binding and permit['dependency_hashes']==deps
        assert permit['runtime_freeze_sha256']==plan['freeze_sha256']
        assert load(folder/'runtime_admission.json')['time_binding']==expected_binding
        assert load(folder/'runtime_completion.json')['observation_returncode']==0
    manifest={p['id']:p for p in load(pages)};bindings=[];seeds=set();grouped={}
    for name in sorted(manifest):
        row=manifest[name];rp=source/'raw'/(name+'.json');mp=source/'markdown'/(name+'.md')
        bindings.append(dict(raw=str(rp),raw_sha256=sha(rp),md_sha256=sha(mp),source=row['image'],source_sha256=sha(row['image'])))
        raw=load(rp)
        seeds.update((str(rp),i) for i,b in enumerate(raw['blocks']) if b['type']=='image' and b.get('angle',0)==0)
    assert bindings==census['bindings'] and census['input_pages']==1651
    decisions=census['rows']+census['rejected'];assert len(decisions)==len(seeds)
    assert {(q['raw'],q['owner']) for q in decisions}==seeds
    assert all(q['gate']['accepted'] for q in census['rows']) and all(not q['gate']['accepted'] for q in census['rejected'])
    assert census['rows']==sorted(census['rows'],key=lambda q:(q['view_pixel_sha256'],q['owner']))
    assert census['risk_owners']==len(census['rows']) and census['risk_pages']==len({q['source_sha256'] for q in census['rows']})
    queue=[];counts={}
    for q in census['rows']:
        admitted=len(queue)<census['budget'] and counts.get(q['source_sha256'],0)<4
        assert q['budget_admitted']==admitted
        if admitted:counts[q['source_sha256']]=counts.get(q['source_sha256'],0)+1;queue.append(dict(q,ordinal=len(queue)))
    assert queue==census['queue'] and len(prepared)==len(queue)
    import torch
    from transformers import AutoProcessor
    torch.set_num_threads(2);processor=AutoProcessor.from_pretrained(params('text')['model'],local_files_only=True)
    for q,original in zip(prepared,queue):
        assert all(q[k]==v for k,v in original.items())
        rp=Path(q['raw']);raw=load(rp);md=(source/'markdown'/(rp.stem+'.md')).read_bytes().decode()
        assert sha(rp)==q['raw_sha256'] and sha(q['source'])==q['source_sha256']
        with Image.open(q['source']) as im:im=im.convert('RGB');verdict=gate(im,raw['blocks'],q['owner'],md);crop=im.crop(verdict['rect'])
        assert verdict==q['gate'] and pix(crop)==q['view_pixel_sha256']
        data,prompt,_,_=helper().prepare_for_extract(crop,[ContentBlock(type='text',bbox=[0.,0.,1.,1.],angle=0)])
        assert data[0]==(folder/f'prepared{q["ordinal"]}.bin').read_bytes()
        assert sha(folder/f'prepared{q["ordinal"]}.bin')==q['prepared_sha256']
        pim=Image.open(io.BytesIO(data[0])).convert('RGB')
        assert q['pixel_sha256']==pix(pim) and q['prepared_size']==list(pim.size) and q['identity']==key(pim.size,pix(pim),'text')
        assert q['parameters']==params('text') and q['prompt']==prompt[0]==prompts('text')[0]['text']
        messages=[dict(role='system',content='You are a helpful assistant.'),dict(role='user',content=[dict(type='image',image=pim),dict(type='text',text=q['prompt'])])]
        v=processor(text=[processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)],images=[pim],return_tensors='pt')
        assert q['processor']==dict(prompt_tokens=int(v['input_ids'].shape[-1]),grid=v['image_grid_thw'].tolist(),tensor_sha256=hashlib.sha256(v['pixel_values'].numpy().tobytes()).hexdigest())
        grouped.setdefault(rp.stem,[]).append(q)
    execution=load(observation/'execution.json');budget=load(observation/'budget.json');service=load(observation/'service.json')
    assert execution['status']=='COMPLETE' and execution['GT_hidden'] and execution['retry']==execution['unknown_usage_attempts']==0
    assert budget['maximum']==census['budget'] and budget['reserved']==execution['actual_HTTP']==len(prepared)==len(responses)<=8
    assert budget['sources']==counts and all(v==1 for v in budget['owners'].values())
    assert len(budget['identities'])==len(set(budget['identities']))==len(prepared)
    assert service['read_only_checkpoint_mount'] and service['model']==params('text')['model']
    verify_hashes(service['processor_hashes'])
    if frozen is not None:
        assert service['container_id']==frozen['services'][plan['brace_gpu']]['container_id']
        assert service['weight_sha256']==frozen['weight_sha256'] and service['model']==frozen['model']
    wires=[]
    for index in observation.glob('wire_*/index.jsonl'):
        for line in index.read_text().splitlines():wires.append((index.parent,json.loads(line)))
    assert len(wires)==len(prepared);response_by_ordinal={r['ordinal']:r for r in responses}
    assert len({r['request_sha256'] for _,r in wires})==len(response_by_ordinal)==len(prepared)
    audits=[json.loads(line) for line in (observation/'audit/http.jsonl').read_text().splitlines()]
    configured={r['request_sha256']:r for r in audits if r['stage']=='configured'}
    consumed={r['request_sha256']:r for r in audits if r['stage']=='consumed'}
    assert configured.keys()==consumed.keys()=={r['request_sha256'] for r in responses}
    for q in prepared:
        rec=response_by_ordinal[q['ordinal']]
        matches=[(p,r) for p,r in wires if load(p/r['response_file'])==rec['response']]
        assert len(matches)==1;wf,wi=matches[0]
        cf,cu=configured[rec['request_sha256']],consumed[rec['request_sha256']]
        assert cf['parameters']==q['parameters'] and cf['prompts']==prompts('text')
        assert len(cf['images'])==1 and cf['images'][0]['pixel_sha256']==q['pixel_sha256'] and cu['response']==rec['response']
        assert wi['status_code']==200 and sha(wf/wi['request_file'])==wi['request_sha256'] and sha(wf/wi['response_file'])==wi['response_sha256']
        req,res=load(wf/wi['request_file']),load(wf/wi['response_file'])
        assert {k:v for k,v in req.items() if k!='messages'}==params('text')
        ims=[c['image_url']['url'] for m in req['messages'] if isinstance(m['content'],list) for c in m['content'] if c['type']=='image_url']
        texts=[c['text'] for m in req['messages'] if isinstance(m['content'],list) for c in m['content'] if c['type']=='text']
        assert len(ims)==1 and base64.b64decode(ims[0].split(',',1)[1])==(folder/f'prepared{q["ordinal"]}.bin').read_bytes() and texts==[q['prompt']]
        assert rec['response']==res and res['model']==service['model'] and rec['text']==res['choices'][0]['message']['content']
        assert rec['finish']==res['choices'][0]['finish_reason'] and res['usage']['prompt_tokens']==q['processor']['prompt_tokens']
    for k in ['prompt_tokens','completion_tokens']:assert sum(r['response']['usage'][k] for r in responses)==execution[k]
    dest=(folder/'selected_predictions') if not historical else Path(research_predictions)
    owners=0;changed=[]
    for name in sorted(manifest):
        rp=source/'raw'/(name+'.json');mp=source/'markdown'/(name+'.md');rb,mb=rp.read_bytes(),mp.read_bytes()
        nr,nm,count=reconstruct(rb,mb,grouped.get(name,[]),response_by_ordinal);owners+=count
        if (nr,nm)!=(rb,mb):changed.append(name)
        for sub,path,data in [('raw',rp,nr),('markdown',mp,nm)]:
            target=dest/sub/path.name;assert target.is_file() and not target.is_symlink() and target.read_bytes()==data
            if bridge is not None and not historical:assert (Path(bridge)/'predictions'/sub/path.name).read_bytes()==data
    for sub in ['raw','markdown']:assert len(list((dest/sub).iterdir()))==1651
    costs=dict(actual_attempts=execution['actual_HTTP'],extra_prompt_tokens=execution['prompt_tokens'],extra_completion_tokens=execution['completion_tokens'],
        missing_usage=0,failed=0,retries=0,wall_seconds=execution['wall_seconds'],initialization_seconds=load(folder/'initialization.json')['wall_seconds'],
        risk_pages=census['risk_pages'],risk_owners=census['risk_owners'],changed_pages=len(changed),selected_owners=owners,
        maximum_attempts=census['budget'],source_cap=4,owner_cap=1,model=service['model'],GPU_busy_seconds=None)
    return costs,time.monotonic()-began

def materialize_brace(folder,target):
    folder,target=Path(folder),Path(target);assert not target.exists();target.mkdir()
    for sub in ['raw','markdown']:
        dest=target/'predictions'/sub;dest.mkdir(parents=True)
        for p in (folder/'selected_predictions'/sub).iterdir():assert p.is_file() and not p.is_symlink();os.link(p,dest/p.name)
    save(target/'receipt.json',dict(source=str(folder),kind='verified_fresh_brace_materialization',new_HTTP=0))
