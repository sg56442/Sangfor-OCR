"""Fresh bounded prose admission; verify source views, wire, costs and all output bytes."""
import base64
import collections
import hashlib
import io
import json
from pathlib import Path
import sys
import time
from PIL import Image
from phase2_final_runtime_v1 import ROOT, PYTHON, inside, load, save, sha, verify_hashes
from phase2_final_brace_v1 import image_directory
sys.path[:0] = [str(ROOT/'code/experimenter'), str(ROOT/'code/runtime')]
from finite_request_identity_0101_v1 import params, prompts, pix, key, helper
from mineru_vl_utils.structs import ContentBlock
from dependency_lock_0111_v1 import verify as verify_dependencies
from prose_geometry_0143_v1 import union, intersection, parse, proposals
from prose_expand_0142_v1 import expand
from prose_order_resolve_0145_v1 import resolve
from prose_select_0143_v1 import edit
from boxed_diagram_0133_v1 import view
from phase2_uncovered_parallel_census_v1 import page_row

RUNNER = 'code/experimenter/prose_runtime_0145_v1.py'
TIME_GATE = 'code/experimenter/phase2_final_time_gate_v1.py'


def binding(source, pages, folder, gpu, budget):
    source, pages, folder = [Path(p).resolve() for p in [source,pages,folder]]
    images = {p.stem:p for p in pages.iterdir() if p.is_file()}
    files = sorted((source/'raw').glob('*.json'))
    assert len(files) == 1651
    fingerprints = [(p.name,sha(p),sha(source/'markdown'/(p.stem+'.md')),sha(images[p.stem])) for p in files]
    return dict(max_plan_rows=0,kind='prose_current_input',inputs=str(source),pages=str(pages),out=str(folder),
                gpu=str(gpu),budget=budget,ledger=None,max_new_http=32,
                input_sha256=hashlib.sha256(json.dumps(fingerprints).encode()).hexdigest())


def prepare_prose_recovery(plan, frozen):
    source = inside(plan['output'])/'B_before_prose_recovery/predictions'
    folder = inside(plan['prose_output'])
    assert folder.parent == ROOT/'runs' and not folder.exists()
    images = image_directory(inside(frozen['pages']))
    gpu, budget = plan['prose_gpu'], frozen['prose_recovery_budget']
    assert gpu == plan['gpu'] and budget == 32
    deps = load(inside(frozen['prose_recovery_dependencies']))['files']
    verify_hashes(deps)
    assert all(frozen['source_hashes'].get(p) == h for p,h in deps.items())
    hashes = dict(deps)
    for name in [RUNNER,TIME_GATE,'scripts/phase2_final_prose_recovery_v1.py']:
        hashes[str(ROOT/name)] = sha(ROOT/name)
        assert frozen['source_hashes'][str(ROOT/name)] == sha(ROOT/name)
    control = load(ROOT/'control/final_validation_plan.json')
    permit = dict(mode='final_validation',approved=True,approved_by='RSI',phase=control['phase'],
                  run_binding=binding(source,images,folder,gpu,budget),source_hashes=hashes,
                  dependency_hashes=deps,campaign_deadline=control['deadline_at'],not_before=control['start_at'],
                  runtime_freeze_sha256=plan['freeze_sha256'])
    path = inside(plan['output'])/'prose_recovery_final_permit.json'
    assert not path.exists()
    save(path,permit)
    return [PYTHON,'-B',RUNNER,'--inputs',source,'--pages',images,'--out',folder,'--gpu',gpu,'--budget',str(budget),
            '--final-validation-admission',path,'--final-validation-sha256',sha(path)]


def source_plan(rows):
    result = []
    for row in rows:
        if not row['groups']:
            continue
        raw = load(row['raw'])
        with Image.open(row['source']) as original:
            image = original.convert('RGB')
            w,h = image.size
            box = union([v for group in row['groups'] for v in group])
            box = [box[0]/w,box[1]/h,box[2]/w,box[3]/h]
            if any(v['type']=='table' and intersection(box,v['bbox'])>0 for v in raw['blocks']):
                result.append(dict(**row,decision='table_fallback'))
                continue
            for _ in raw['blocks']:
                new = union([box]+[v['bbox'] for v in raw['blocks'] if intersection(box,v['bbox'])>0])
                if new == box:
                    break
                box = new
            box,proof = expand(image,box,raw['blocks'])
            result.append(dict(**row,decision='ready',source_bbox=box,expansion=proof))
    return result


def verify_prose_recovery(folder, source, pages, *, plan=None, frozen=None, research_target=None, current_census=None):
    """Archived observations may be reverified only without a final plan or freeze."""
    began = time.monotonic()
    folder, source, pages = [Path(p).resolve() for p in [folder,source,pages]]
    research = research_target is not None
    assert not research or plan is None and frozen is None
    assert current_census is None or research
    target = Path(research_target).resolve() if research else folder/'selected_predictions'
    admission, completed = load(folder/'admission.json'), load(folder/'completion.json')
    original_source = Path(admission['binding']['inputs'])
    assert load(folder/'runtime_inputs.json')['inputs'] == str(original_source)
    assert completed['status'] == 'COMPLETE'
    assert admission['binding'] == binding(original_source,image_directory(pages),folder,admission['binding']['gpu'],32)
    verify_dependencies(folder/'dependencies.json')
    if frozen is not None:
        assert plan is not None and not research and source == original_source
        assert admission['entry'] == str(ROOT/RUNNER)
        assert admission['binding']['gpu'] == plan['prose_gpu'] == plan['gpu']
        assert admission['binding']['budget'] == frozen['prose_recovery_budget'] == 32
        permit_path = inside(plan['output'])/'prose_recovery_final_permit.json'
        permit = load(permit_path)
        assert admission['permit'] == str(permit_path) and admission['permit_sha256'] == sha(permit_path)
        assert permit['run_binding'] == admission['binding'] and permit['runtime_freeze_sha256'] == plan['freeze_sha256']
        deps = load(folder/'dependencies.json')['files']
        assert deps == load(inside(frozen['prose_recovery_dependencies']))['files']
        assert all(frozen['source_hashes'].get(p) == h for p,h in deps.items())
    census = load(Path(current_census)/'census.json' if current_census else folder/'census/census.json')
    assert census['status']=='COMPLETE' and census['pages']==census['expected_pages']==1651 and census['HTTP']==0 and census['GT_hidden']
    manifest = {str(Path(p['image'])):p for p in load(pages)}
    assert len(manifest)==len(census['rows'])==1651
    assert {r['source'] for r in census['rows']} == manifest.keys()
    assert census['rows'] == sorted(census['rows'],key=lambda r:r['source_sha256'])
    for row in census['rows']:
        page = manifest[row['source']]
        assert row['raw']==str(source/'raw'/(page['id']+'.json'))
        assert row['raw_sha256']==sha(row['raw']) and row['source_sha256']==sha(row['source'])
        if row['groups']:
            assert row == page_row((row['raw'],row['source']))
    expected_plan = source_plan(census['rows'])
    archived_plan = load(folder/'plan.json')
    outcomes = load(folder/'outcomes.json')
    removed_nonexecuted = []
    if research:
        wanted = {r['source'] for r in expected_plan}
        archived_sources = {r['source'] for r in archived_plan}
        assert wanted <= archived_sources
        for row,result in zip(archived_plan,outcomes):
            assert row['source']==result['source']
            if row['source'] not in wanted:
                assert row['decision']=='table_fallback' and result['decision']=='table_fallback'
                assert 'layout' not in result and 'text' not in result
                removed_nonexecuted.append(dict(source_sha256=row['source_sha256'],reason='prior_table_fallback_no_observation'))
        archived_plan = [r for r in archived_plan if r['source'] in wanted]
        outcomes = [r for r in outcomes if r['source'] in wanted]
    def without_raw(rows):
        return [{k:v for k,v in row.items() if k!='raw'} for row in rows]
    assert without_raw(expected_plan) == without_raw(archived_plan)
    assert len(outcomes) == len(expected_plan)
    ledger = load(folder/'budget_ledger.json')
    assert ledger['maximum']==32 and ledger['reserved']==completed['new_HTTP']<=32
    assert all(v<=4 for v in ledger['sources'].values()) and all(v<=2 for v in ledger['owners'].values())
    assert len(set(ledger['identities']))==len(ledger['identities'])==ledger['reserved']
    stages = sorted(folder.glob('stage*'),key=lambda p:int(p.name[5:]))
    import torch
    from transformers import AutoProcessor
    torch.set_num_threads(2)
    processor = AutoProcessor.from_pretrained(params('text')['model'],local_files_only=True)
    verified, costs = {}, []
    for stage in stages:
        verify_dependencies(stage/'dependencies.json')
        q = load(stage/'prepared.json')[0]
        task = load(stage/'task.json')['task']
        assert task in ['text','[layout]'] and q['ordinal']==0
        rp = source/'raw'/Path(q['raw']).name
        assert sha(rp)==q['raw_sha256'] and sha(q['source'])==q['source_sha256']
        assert q['parameters']==params(task) and q['prompt']==prompts(task)[0]['text']
        with Image.open(q['source']) as im:
            im = im.convert('RGB')
            gate = view(im,dict(type='image',bbox=q['source_bbox'],angle=0))
            crop = im.crop(gate['rect'])
        assert gate==q['gate'] and list(gate['rect'])==q['mapping']['rect']
        data = helper().prepare_for_layout(crop) if task=='[layout]' else helper().prepare_for_extract(crop,[ContentBlock(type='text',bbox=[0.,0.,1.,1.],angle=0)])[0][0]
        assert data==(stage/'prepared0.bin').read_bytes() and sha(stage/'prepared0.bin')==q['prepared_sha256']
        pim = Image.open(io.BytesIO(data)).convert('RGB')
        assert pix(pim)==q['pixel_sha256'] and list(pim.size)==q['prepared_size'] and key(pim.size,pix(pim),task)==q['identity']
        rect=gate['rect']
        assert q['mapping']['affine']==[crop.width/pim.width,0,rect[0],0,crop.height/pim.height,rect[1]]
        messages=[dict(role='system',content='You are a helpful assistant.'),dict(role='user',content=[dict(type='image',image=pim),dict(type='text',text=q['prompt'])])]
        values=processor(text=[processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)],images=[pim],return_tensors='pt')
        assert q['processor']==dict(prompt_tokens=int(values['input_ids'].shape[-1]),grid=values['image_grid_thw'].tolist(),tensor_sha256=hashlib.sha256(values['pixel_values'].numpy().tobytes()).hexdigest())
        service=load(stage/'service.json')
        assert service['read_only_checkpoint_mount'] and service['model']==params(task)['model']
        verify_hashes(service['processor_hashes'])
        if frozen is not None:
            assert service['container_id']==frozen['services'][plan['prose_gpu']]['container_id'] and service['weight_sha256']==frozen['weight_sha256']
            assert load(stage/'time_binding.json')==admission
        execution=load(stage/'execution.json')
        local=load(stage/'budget.json')
        assert execution['GT_hidden'] and execution['retry']==0 and execution['actual_HTTP']==local['reserved']<=1
        answers=load(stage/'responses.json') if (stage/'responses.json').exists() else []
        wires=[]
        for index in stage.glob('wire_*/index.jsonl'):
            wires.extend((index.parent,json.loads(line)) for line in index.read_text().splitlines())
        assert len(wires)<=execution['actual_HTTP']
        audits=[json.loads(line) for line in (stage/'audit/http.jsonl').read_text().splitlines()] if (stage/'audit/http.jsonl').exists() else []
        configured={v['request_sha256']:v for v in audits if v['stage']=='configured'}
        consumed={v['request_sha256']:v for v in audits if v['stage']=='consumed'}
        answer=answers[0] if answers else None
        if answer and answer.get('consumed'):
            assert len(answers)==len(wires)==1
            wf,wire=wires[0]
            assert wire['status_code']==200 and sha(wf/wire['request_file'])==wire['request_sha256'] and sha(wf/wire['response_file'])==wire['response_sha256']
            request,response=load(wf/wire['request_file']),load(wf/wire['response_file'])
            assert {k:v for k,v in request.items() if k!='messages'}==params(task)
            items=[c for m in request['messages'] if isinstance(m['content'],list) for c in m['content']]
            images=[c['image_url']['url'] for c in items if c['type']=='image_url']
            assert len(images)==1 and base64.b64decode(images[0].split(',',1)[1])==data
            assert [c['text'] for c in items if c['type']=='text']==[q['prompt']]
            cf,cu=configured[answer['request_sha256']],consumed[answer['request_sha256']]
            assert cf['parameters']==params(task) and cf['prompts']==prompts(task) and cf['images'][0]['pixel_sha256']==q['pixel_sha256']
            assert response==answer['response']==cu['response'] and response['model']==service['model']
            assert answer['text']==response['choices'][0]['message']['content'] and answer['finish']==response['choices'][0]['finish_reason']
            assert response['usage']['prompt_tokens']==q['processor']['prompt_tokens']
            for key_name in ['prompt_tokens','completion_tokens']:
                assert execution[key_name]==response['usage'][key_name]
        verified[str(stage)] = dict(prepared=q,answer=answer,task=task,actual_attempts=execution['actual_HTTP'])
        costs.append(execution)
    assert sum(c['actual_HTTP'] for c in costs)==ledger['reserved']
    billed = [v['prepared'] for v in verified.values() if v['actual_attempts']]
    assert ledger['identities']==[q['identity'] for q in billed]
    assert ledger['sources']==dict(collections.Counter(q['source_sha256'] for q in billed))
    assert ledger['owners']==dict(collections.Counter(q['source_sha256']+':'+str(q['owner']) for q in billed))
    changes={}
    for row,result in zip(expected_plan,outcomes):
        assert row['source']==result['source']
        if row['decision']!='ready':
            assert result['decision']==row['decision']
            continue
        layout=result['layout']
        if 'stage' not in layout:
            assert layout['reason'] in ['budget_cap_fallback','previous_effective_identity_fallback']
            continue
        observed=verified[layout['stage']]
        q,answer=observed['prepared'],observed['answer']
        assert observed['task']=='[layout]' and q['source_bbox']==row['source_bbox'] and q['owner']=='risk_context'
        if answer is None or answer.get('finish')!='stop':
            continue
        raw=load(row['raw'])
        with Image.open(row['source']) as im:
            try:
                blocks=parse(answer['text'],q['mapping']['rect'],im.size)
                expected=proposals(blocks,raw['blocks'],[b for g in row['groups'] for b in g],im.size)
            except (AssertionError,ValueError):
                assert result['fallback']=='layout_parse'
                continue
            md=(source/'markdown'/(Path(row['raw']).stem+'.md')).read_bytes().decode()
            expected=[resolve(p,raw['blocks'],im,md) for p in expected]
        # Old second-input proposals are research evidence; resolve current fixed order here.
        if not research:
            assert expected==result['proposals']
        assert len(expected)==len(result['text'])
        for proposal,returned in zip(expected,result['text']):
            meta=returned['observation']
            if 'stage' not in meta:
                assert meta['reason'] in ['budget_cap_fallback','previous_effective_identity_fallback']
                continue
            observed=verified[meta['stage']]
            prepared,answer=observed['prepared'],observed['answer']
            assert observed['task']=='text' and prepared['source_bbox']==proposal['source_bbox']
            assert prepared['owner']=='text_group:'+hashlib.sha256(json.dumps(proposal['source_bbox']).encode()).hexdigest()
            if answer and answer.get('finish')=='stop':
                changes.setdefault(Path(row['raw']).stem,[]).append((proposal,answer))
    changed,accepted=[],0
    for rp in sorted((source/'raw').glob('*.json')):
        mp=source/'markdown'/(rp.stem+'.md')
        rb,md=rp.read_bytes().decode(),mp.read_bytes().decode()
        for proposal,answer in sorted(changes.get(rp.stem,[]),key=lambda x:(x[0]['replace_owners'] or [x[0]['insert_before']])[0],reverse=True):
            try:
                rb,md,receipt=edit(rb,md,proposal,answer,True)
                assert receipt['non_target_bytes_preserved']
                accepted+=1
            except (AssertionError,ValueError,KeyError,IndexError):
                pass
        for sub,p,data in [('raw',rp,rb.encode()),('markdown',mp,md.encode())]:
            dest=target/sub/p.name
            assert dest.is_file() and not dest.is_symlink() and dest.read_bytes()==data,dest
        if (rb.encode(),md.encode())!=(rp.read_bytes(),mp.read_bytes()):
            changed.append(rp.stem)
    assert all(len(list((target/sub).iterdir()))==1651 for sub in ['raw','markdown'])
    result=dict(actual_attempts=ledger['reserved'],extra_prompt_tokens=sum(v['prompt_tokens'] for v in costs),
                extra_completion_tokens=sum(v['completion_tokens'] for v in costs),
                missing_usage=sum(v['unknown_usage_attempts'] for v in costs),failed=sum(v['status']!='COMPLETE' for v in costs),
                non_stop=sum(bool(v['answer']) and v['answer'].get('finish')!='stop' for v in verified.values()),
                retries=0,wall_seconds=completed['wall_seconds'],prepare_seconds=completed['prepare_seconds'],
                HTTP_loop_seconds=sum(v['wall_seconds'] for v in costs),maximum_attempts=32,source_cap=4,owner_cap=2,
                risk_pages=census['risk_pages'],risk_groups=census['risk_groups'],changed_pages=len(changed),
                selected_groups=accepted,model=params('text')['model'],GPU_busy_seconds=None,
                research_observation_replay=research,removed_nonexecuted_research_risks=removed_nonexecuted)
    return result,time.monotonic()-began
