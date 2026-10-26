"""Bounded same-MinerU complete text groups; full census, wire and output verification."""
import base64
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import time
from PIL import Image
from phase2_final_runtime_v1 import ROOT, PYTHON, inside, load, save, sha, now, verify_hashes
sys.path[:0] = [str(ROOT/'code/experimenter'), str(ROOT/'code/runtime')]
from skew_group_0146_v1 import risk
from skew_select_0146_v1 import select
from skew_timegate_0146_v2 import input_hash, source_hashes
from finite_request_identity_0101_v1 import helper, pix, key, params, prompts
from mineru_vl_utils.structs import ContentBlock

RUNNER = 'code/experimenter/skew_runtime_0146_v2.py'
DEPENDENCIES = 'code/experimenter/skew_frozen_0146_v2.json'


def image_directory(pages):
    rows = load(pages)
    assert len(rows) == 1651
    dirs = {Path(p['image']).parent for p in rows}
    assert len(dirs) == 1
    return dirs.pop()


def binding(source, pages, folder, gpu, ledger, ledger_id, budget=4):
    lease = load(ROOT/'control/gpu_leases.json')[gpu]
    return dict(kind='skew_current_input', inputs=str(Path(source).resolve()),
        pages=str(image_directory(pages)), out=str(Path(folder).resolve()), gpu=gpu,
        budget=budget, ledger=str(Path(ledger).resolve()), ledger_id=ledger_id,
        source_cap=4, owner_cap=1, retry=0, input_sha256=input_hash(source,image_directory(pages)),
        dependency_lock_sha256=sha(ROOT/DEPENDENCIES),
        service=dict(endpoint=lease['endpoint'],container_id=lease['container_id']))


def prepare(plan, frozen):
    started = time.monotonic()
    assert frozen['skew_runner'] == RUNNER and frozen['skew_budget'] == 2
    out = inside(plan['output']); folder = inside(plan['skew_output'])
    source = out/'B_before_skew/predictions'
    assert folder.parent == ROOT/'runs' and not folder.exists()
    ledger = out/'skew_budget.json'; permit = out/'skew_final_permit.json'
    assert not ledger.exists() and not permit.exists()
    ledger_id = Path(plan['output']).name+'_skew'
    save(ledger,dict(ledger_id=ledger_id,maximum=2,reserved=0,sources={},owners={},identities=[]))
    request = binding(source, inside(frozen['pages']), folder, plan['gpu'], ledger, ledger_id, budget=2)
    control=load(ROOT/'control/final_validation_plan.json');phase=load(ROOT/'control/phase2_plan.json')
    assert control['runtime_freeze']==plan['freeze'] and control['runtime_freeze_sha256']==plan['freeze_sha256']
    hashes=source_hashes(ROOT)
    assert all(frozen['source_hashes'].get(p)==h for p,h in hashes.items())
    save(permit,dict(mode='final_validation',approved=True,approved_by='RSI',phase=phase['phase'],
        run_binding=request,source_hashes=hashes,campaign_deadline=phase['deadline_at'],
        not_before=control['start_at'],active_freeze=control['runtime_freeze'],active_freeze_sha256=control['runtime_freeze_sha256']))
    from skew_timegate_0146_v2 import check
    check(ROOT,dict(binding=request,permit=str(permit),permit_sha256=sha(permit),dependency_lock=str(ROOT/DEPENDENCIES),ledger=str(ledger)))
    save(out/'skew_prepare.json',dict(at=now(),seconds=time.monotonic()-started,binding=request,permit_sha256=sha(permit)))
    return [PYTHON,'-B',RUNNER,'--inputs',str(source),'--pages',str(image_directory(inside(frozen['pages']))),
        '--out',str(folder),'--gpu',plan['gpu'],'--budget','2','--ledger',str(ledger),
        '--dependency-lock',str(ROOT/DEPENDENCIES),'--final-validation-admission',str(permit),'--final-validation-sha256',sha(permit)]


def verify(folder, source, pages, *, plan=None, frozen=None):
    started=time.monotonic();folder,source,pages=map(lambda p:Path(p).resolve(),[folder,source,pages])
    census=load(folder/'census.json');qs=load(folder/'prepared.json');answers=load(folder/'responses.json')
    cfg=load(folder/'time_binding.json');ledger=load(folder/'budget.json');completion=load(folder/'completion.json')
    assert load(folder/'runtime_inputs.json')['inputs']==str(source)
    verify_hashes(load(folder/'dependencies.json')['files'])
    assert cfg['binding']==binding(source,pages,folder,cfg['binding']['gpu'],folder/'budget.json',ledger['ledger_id'],ledger['maximum'])
    assert completion['status']=='COMPLETE' and completion['GT_history_hidden'] and census['GT_hidden']
    if frozen is not None:
        assert plan is not None and cfg['binding']['gpu']==plan['gpu']
        assert cfg['binding']['budget']==frozen['skew_budget']==2
        assert cfg['dependency_lock']==str(ROOT/DEPENDENCIES)
        assert all(frozen['source_hashes'].get(p)==h for p,h in load(folder/'dependencies.json')['files'].items())
        permit=load(inside(plan['output'])/'skew_final_permit.json')
        assert permit['active_freeze_sha256']==plan['freeze_sha256'] and permit['run_binding']==cfg['binding']
        assert permit['source_hashes']==source_hashes(ROOT) and sha(cfg['permit'])==cfg['permit_sha256']
    manifest={p['id']:p for p in load(pages)};locked={};counts={};rows=[]
    for name in sorted(manifest):
        rp=source/'raw'/(name+'.json');mp=source/'markdown'/(name+'.md');image=Path(manifest[name]['image'])
        for p in [rp,mp,image]:locked[str(p)]=sha(p)
        blocks=load(rp)['blocks']
        valid=all(isinstance(b,dict) and isinstance(b.get('bbox'),list) and len(b['bbox'])==4 and
            all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in b['bbox']) and
            b['bbox'][2]>b['bbox'][0] and b['bbox'][3]>b['bbox'][1] for b in blocks)
        with Image.open(image) as im: verdict=risk(im,blocks) if valid else dict(accepted=False,reason='invalid_geometry')
        counts[verdict['reason']]=counts.get(verdict['reason'],0)+1
        if verdict['reason'] in ['overlap_with_source_skew','source_skew_not_supported']:
            rows.append(dict(source=str(image),raw=str(rp),source_sha256=locked[str(image)],gate=verdict))
    assert len(manifest)==census['pages']==1651 and locked==census['bindings'] and counts==census['counts'] and rows==census['rows']
    candidates=sorted([r for r in rows if r['gate']['accepted']],key=lambda r:r['source_sha256'])[:ledger['maximum']]
    assert len(qs)<=len(candidates)
    grouped={};processor=None
    if qs:
        import torch
        from transformers import AutoProcessor
        torch.set_num_threads(2);processor=AutoProcessor.from_pretrained(params('text')['model'],local_files_only=True)
    for q in qs:
        r=candidates[q['ordinal']]
        assert all(q[k]==r[k] for k in ['source','raw','source_sha256','gate'])
        assert q['owner']=='complete_text_group' and q['block']==dict(type='text',bbox=r['gate']['bbox'],angle=0)
        assert sha(q['raw'])==q['raw_sha256']
        with Image.open(q['source']) as im:
            im=im.convert('RGB');data,ps,_,_=helper().prepare_for_extract(im,[ContentBlock(**q['block'])])
        assert data[0]==(folder/f'prepared{q["ordinal"]}.bin').read_bytes() and sha(folder/f'prepared{q["ordinal"]}.bin')==q['prepared_sha256']
        pim=Image.open(io.BytesIO(data[0])).convert('RGB')
        assert q['pixel_sha256']==pix(pim) and q['prepared_size']==list(pim.size) and q['identity']==key(pim.size,pix(pim),'text')
        assert q['parameters']==params('text') and q['prompt']==ps[0]==prompts('text')[0]['text']
        messages=[dict(role='system',content='You are a helpful assistant.'),dict(role='user',content=[dict(type='image',image=pim),dict(type='text',text=q['prompt'])])]
        v=processor(text=[processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)],images=[pim],return_tensors='pt')
        assert q['processor']==dict(prompt_tokens=int(v['input_ids'].shape[-1]),grid=v['image_grid_thw'].tolist(),tensor_sha256=hashlib.sha256(v['pixel_values'].numpy().tobytes()).hexdigest())
        assert q['processor']['prompt_tokens']+4096<=8192
        grouped.setdefault(Path(q['raw']).stem,[]).append(q)
    execution=load(folder/'execution.json');n=execution['actual_HTTP']
    assert n==completion['new_HTTP']==ledger['reserved']<=len(qs)<=4
    assert execution['GT_hidden'] and execution['status'] in ['COMPLETE','COMPLETE_NO_REQUEST']
    assert len(answers)==n and len({q['ordinal'] for q in answers})==n
    assert len(ledger['identities'])==len(set(ledger['identities']))==n and all(v<=1 for v in ledger['owners'].values()) and all(v<=4 for v in ledger['sources'].values())
    if n:
        service=load(folder/'service.json');assert service['read_only_checkpoint_mount']
        assert service['weight_sha256']=='01dcb5addfa1d6133fd0930e79fa2484817cb0228af21cb4917fa73d04fa3147' and service['model']==params('text')['model']
        verify_hashes(service['processor_hashes'])
        if frozen is not None:assert service['container_id']==frozen['services'][plan['gpu']]['container_id']
    audits=[json.loads(line) for line in (folder/'audit/http.jsonl').read_text().splitlines()] if n else []
    configured={r['request_sha256']:r for r in audits if r['stage']=='configured'};consumed={r['request_sha256']:r for r in audits if r['stage']=='consumed'}
    assert len(configured)==n
    wires=[]
    for index in folder.glob('wire_*/index.jsonl'):
        wires.extend((index.parent,json.loads(line)) for line in index.read_text().splitlines())
    used=set();known=0;tokens=dict(prompt_tokens=0,completion_tokens=0)
    for rec in answers:
        q=next(q for q in qs if q['ordinal']==rec['ordinal'])
        if rec['status']!='CONSUMED':
            assert rec['status']=='FAILED';continue
        known+=1;cf=configured[rec['request_sha256']];cu=consumed[rec['request_sha256']]
        assert cf['parameters']==q['parameters'] and cf['prompts']==prompts('text') and cu['response']==rec['response']
        assert len(cf['images'])==1 and cf['images'][0]['pixel_sha256']==q['pixel_sha256']
        matches=[(p,w) for p,w in wires if w.get('response_file') and load(p/w['response_file'])==rec['response']]
        assert len(matches)==1;wf,w=matches[0];used.add(w['request_sha256'])
        assert w['status_code']==200 and sha(wf/w['request_file'])==w['request_sha256'] and sha(wf/w['response_file'])==w['response_sha256']
        req,res=load(wf/w['request_file']),load(wf/w['response_file'])
        assert {k:v for k,v in req.items() if k!='messages'}==params('text')
        ims=[c['image_url']['url'] for m in req['messages'] if isinstance(m['content'],list) for c in m['content'] if c['type']=='image_url']
        texts=[c['text'] for m in req['messages'] if isinstance(m['content'],list) for c in m['content'] if c['type']=='text']
        assert len(ims)==1 and base64.b64decode(ims[0].split(',',1)[1])==(folder/f'prepared{q["ordinal"]}.bin').read_bytes() and texts==[q['prompt']]
        assert res['model']==params('text')['model'] and rec['text']==res['choices'][0]['message']['content'] and rec['finish']==res['choices'][0]['finish_reason']
        assert res['usage']['prompt_tokens']==q['processor']['prompt_tokens']
        for k in tokens:tokens[k]+=res['usage'][k]
    assert len(used)==known and len(wires)<=n
    if n:
        assert execution['known_usage_attempts']==known and execution['unknown_usage_attempts']==n-known
        for k,v in tokens.items():assert execution[k]==v
    changed=[];owners=0;dest=folder/'selected_predictions'
    byid={r['ordinal']:r for r in answers}
    for name in sorted(manifest):
        rp=source/'raw'/(name+'.json');mp=source/'markdown'/(name+'.md');rb,mb=rp.read_bytes(),mp.read_bytes();nr,nm=rb,mb
        for q in grouped.get(name,[]):
            rec=byid.get(q['ordinal'])
            if not rec or rec['status']!='CONSUMED':continue
            raw=json.loads(nr);md=nm.decode();decision,reason=select(raw['blocks'],q['gate'],md,rec['text'],rec['finish'])
            if not decision:continue
            oldblocks=json.loads(nr)['blocks']
            for index,para in zip(decision['indices'],decision['paragraphs']):raw['blocks'][index]['content']=para
            for index,(before,after) in enumerate(zip(oldblocks,raw['blocks'])):
                assert {k:v for k,v in before.items() if k!='content'}=={k:v for k,v in after.items() if k!='content'}
                if index not in decision['indices']:assert before==after
            nr=json.dumps(raw,ensure_ascii=False,indent=2).encode();nm=(md[:decision['start']]+decision['replacement']+md[decision['start']+len(decision['span']):]).encode();owners+=len(decision['indices'])
        if (nr,nm)!=(rb,mb):changed.append(name)
        for sub,p,expected in [('raw',rp,nr),('markdown',mp,nm)]:
            actual=dest/sub/p.name;assert actual.is_file() and not actual.is_symlink() and actual.read_bytes()==expected
    assert all(len(list((dest/sub).iterdir()))==1651 for sub in ['raw','markdown'])
    return dict(actual_attempts=n,extra_prompt_tokens=tokens['prompt_tokens'],extra_completion_tokens=tokens['completion_tokens'],
        failed=n-known,missing_usage=n-known,retries=0,maximum_attempts=ledger['maximum'],source_cap=4,owner_cap=1,
        wall_seconds=execution.get('wall_seconds',0),runtime_seconds=completion['wall_seconds']+completion['admission_seconds'],
        changed_pages=changed,selected_owners=owners,risk_pages=sum(r['gate']['accepted'] for r in rows),
        verification_seconds=time.monotonic()-started)


if __name__=='__main__':
    pages=inside(load(ROOT/'control/freezes/phase2_AB_centered_final_v24.json')['pages'])
    results={}
    for arm in ['first','second']:
        folder=ROOT/f'runs/skew_fresh_{arm}_0146_v2';source=Path(load(folder/'runtime_inputs.json')['inputs'])
        results[arm]=verify(folder,source,pages)
    target=ROOT/'reports/rsi_phase2_skew_runtime_verified_v2.json';assert not target.exists()
    save(target,dict(status='PASS_BOTH_COMPLETE_RECONSTRUCTIONS_AND_FRESH_WIRE',at=now(),results=results,verifier_sha256=sha(Path(__file__))))
    print(results)
