"""Initialize fresh mixed-context observations and verify source, transport and edits."""
import base64
import collections
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from phase2_final_runtime_v1 import ROOT, PYTHON, inside, load, save, sha, verify_hashes

ENTRY = 'code/experimenter/mixed_runtime_0117_v3.py'


def mixed_command(plan, frozen, source, mode):
    out = inside(plan['output'])/'B_mixed'
    permit = out/'final_permit.json'
    return [PYTHON, '-B', ENTRY, '--inputs', str(source), '--manifest', str(out/'input_manifest.json'),
            '--out', str(out), '--gpu', plan['mixed_gpu'], '--budget', str(frozen['mixed_budget']),
            '--mode', mode, '--final-mode', '--final-permit', str(permit),
            '--final-permit-sha256', sha(permit)]


def prepare_mixed(plan, frozen, source):
    out = inside(plan['output'])/'B_mixed'
    assert not out.exists()
    out.mkdir(parents=True)
    manifest = out/'input_manifest.json'
    manifest.write_bytes(inside(frozen['pages']).read_bytes())
    start = time.monotonic()
    subprocess.run([PYTHON, '-B', ENTRY, '--inputs', str(source), '--manifest', str(manifest),
                    '--out', str(out), '--gpu', plan['mixed_gpu'], '--budget', str(frozen['mixed_budget']),
                    '--mode', 'init'], cwd=ROOT, check=True, capture_output=True, text=True)
    request = load(out/'permit_request.json')
    for p,h in request['source_hashes'].items():
        assert frozen['source_hashes'].get(p, frozen['source_hashes'].get(str(Path(p).relative_to(ROOT))
            if Path(p).is_relative_to(ROOT) else p)) == h, p
    phase = load(ROOT/'control/phase2_plan.json')
    control = ROOT/'control/final_validation_plan.json'
    permit = dict(request, mode='final_validation', approved=True, approved_by='RSI',
                  phase=phase['phase'], not_before=phase['final_start_at'],
                  campaign_deadline=phase['deadline_at'], final_plan_sha256=sha(control),
                  runtime_freeze=str(inside(plan['freeze'])), runtime_freeze_sha256=plan['freeze_sha256'])
    path = out/'final_permit.json'
    assert not path.exists()
    save(path, permit)
    save(out/'initialization.json', dict(wall_seconds=time.monotonic()-start, new_HTTP=0))
    return mixed_command(plan, frozen, source, 'run')


def materialize_mixed(folder, destination):
    folder, destination = Path(folder), Path(destination)
    assert not destination.exists()
    for sub,ext in [('raw','.json'),('markdown','.md')]:
        target = destination/'predictions'/sub
        target.mkdir(parents=True)
        files = list((folder/'candidate'/sub).glob('*'+ext))
        assert len(files) == 1651
        for p in files:
            assert not p.is_symlink()
            os.link(p, target/p.name)
    save(destination/'binding.json', dict(source=str(folder.resolve()),
        decisions_sha256=sha(folder/'decisions.json'), new_HTTP=0))


def verify_mixed(folder, source, pages, gpu, budget=16, plan=None, frozen=None, bridge=None):
    sys.path[:0] = [str(ROOT/'code/experimenter'), str(ROOT/'code/runtime'), str(ROOT/'code/research')]
    from mixed_runtime_0117_v3 import scan
    from mixed_admission_0117_v3 import binding
    from mixed_compose_0117_v3 import compose_page
    from dependency_lock_0111_v1 import verify
    from finite_request_identity_0101_v1 import helper, pix, key, params, prompts, MODEL
    from phase2_runtime_guard_v1 import WEIGHT
    from mineru_vl_utils.structs import ContentBlock
    from PIL import Image
    folder, source, pages = map(lambda p:Path(p).resolve(), [folder,source,pages])
    local_manifest=folder/'input_manifest.json'
    assert local_manifest.read_bytes()==pages.read_bytes()
    pages=local_manifest
    verify(folder/'dependencies.json')
    current = scan(source, pages)
    census = load(folder/'census.json')
    assert {k:v for k,v in census.items() if k!='CPU_scan_seconds'} == current
    assert current['pages'] == 1651
    admission = binding(source,pages,folder,budget,str(gpu),'B')
    assert load(folder/'admission_binding.json') == admission
    if plan is not None:
        permit = load(folder/'final_permit.json')
        assert permit['approved'] and permit['approved_by']=='RSI' and permit['run_binding']==admission
        assert permit['final_plan_sha256']==sha(ROOT/'control/final_validation_plan.json')
        assert permit['runtime_freeze_sha256']==plan['freeze_sha256']==sha(inside(plan['freeze']))
    state = load(folder/'budget.json')
    assert state['maximum']==budget and 0<=state['reserved']<=budget
    assert all(v<=2 for v in state['by_source'].values())
    assert len(state['owners'])==len({tuple(x) for x in state['owners']})==state['reserved']
    responses = load(folder/'responses.json') if (folder/'responses.json').exists() else []
    assert len({r['ordinal'] for r in responses})==len(responses)
    if not responses:
        resumed = load(folder/'resume.json')
        assert resumed['empty_domain'] or not any(r['context'] for r in current['records'])
        assert resumed['new_HTTP']==state['reserved']==0
    else:
        execution=load(folder/'execution.json')
        assert execution['status']=='COMPLETE' and execution['HTTP']==state['reserved']
        assert execution['blind_retries']==0
    prepared = load(folder/'prepared.json') if (folder/'prepared.json').exists() else []
    byordinal = {p['ordinal']:p for p in prepared}
    auditpath=folder/'audit/http.jsonl'
    audit=[json.loads(s) for s in auditpath.read_text().splitlines()] if auditpath.exists() else []
    configured={r['request_sha256']:r for r in audit if r['stage']=='configured'}
    consumed={r['request_sha256']:r for r in audit if r['stage']=='consumed'}
    assert len(configured)>=state['reserved']>=len(consumed)
    wire_responses={}
    for p in folder.glob('wire_*/index.jsonl'):
        for line in p.read_text().splitlines():
            row=json.loads(line)
            req,resp=p.parent/row['request_file'],p.parent/row['response_file']
            assert sha(req)==row['request_sha256'] and sha(resp)==row['response_sha256']
            body=load(req)
            request_hash=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
            if row['status_code']==200:
                wire_responses[request_hash]=load(resp)
    groups=collections.defaultdict(list)
    costs=dict(actual_attempts=state['reserved'], extra_prompt_tokens=0,extra_completion_tokens=0,
               failed=0,non_stop_decodes=0,selected_blocks=0,selected_pages=0,
               worker_seconds_sum=load(folder/'execution.json').get('worker_inference_wall',0)
               if (folder/'execution.json').exists() else 0)
    if responses:
        service=load(folder/'service.json')
        assert service['model']==MODEL and service['weight_sha256']==WEIGHT and service['read_only_checkpoint_mount']
        if frozen is not None:
            assert service['container_id']==frozen['services'][str(gpu)]['container_id']
    for r in responses:
        assert r['admission_sha256']==sha(folder/'admission_binding.json')
        q=current['records'][r['ordinal']]
        assert q['context'] is not None
        p=byordinal[r['ordinal']]
        with Image.open(q['source']) as image:
            image=image.convert('RGB');box=[round(v*(image.width if i%2==0 else image.height)) for i,v in enumerate(q['context']['bbox'])]
            data,ps,_,_=helper().prepare_for_extract(image.crop(box),[ContentBlock(type='text',bbox=[0.,0.,1.,1.],angle=0)])
        assert box==p['box'] and data[0]==(folder/('prepared'+str(r['ordinal'])+'.bin')).read_bytes()
        im=Image.open(io.BytesIO(data[0])).convert('RGB')
        assert pix(im)==p['pixel_sha256'] and list(im.size)==p['prepared_size']
        assert p['identity']==key(im.size,pix(im),'text') and ps[0]==p['prompt']
        if r.get('consumed'):
            c=configured[r['request_sha256']];v=consumed[r['request_sha256']]['response']
            assert c['parameters']==params('text') and c['prompts']==prompts('text')
            assert c['images'][0]['encoded_sha256']==sha(folder/('prepared'+str(r['ordinal'])+'.bin'))
            assert wire_responses[r['request_sha256']]==v and v['model']==MODEL
            assert v['choices'][0]['message']['content']==r['text'] and v['choices'][0]['finish_reason']==r['finish']
            assert v['usage']==r['usage'] and r['usage']['prompt_tokens']==p['prompt_tokens']
            costs['extra_prompt_tokens']+=r['usage']['prompt_tokens']
            costs['extra_completion_tokens']+=r['usage']['completion_tokens']
            costs['non_stop_decodes']+=r['finish']!='stop'
        else:
            costs['failed']+=1
        groups[q['page']].append((r['ordinal'],q['target'],q['context']['indices'],r))
    decisions=[];changed=[];ids={p['id'] for p in load(pages)}
    for sub,ext in [('raw','.json'),('markdown','.md')]:
        assert {p.stem for p in (folder/'candidate'/sub).glob('*'+ext)}==ids
    for name in ids:
        rp,mp=source/'raw'/(name+'.json'),source/'markdown'/(name+'.md')
        raw,md=load(rp),mp.read_bytes()
        expected,text,ds=compose_page(raw,md,groups.get(name,[]))
        decisions.extend(dict(page=name,**d) for d in ds)
        assert expected==load(folder/'candidate/raw'/(name+'.json'))
        assert text==(folder/'candidate/markdown'/(name+'.md')).read_bytes()
        selected=sum(d['selected'] for d in ds);costs['selected_blocks']+=selected
        if selected:changed.append(name)
        for sub,ext in [('raw','.json'),('markdown','.md')]:
            p=folder/'candidate'/sub/(name+ext)
            assert not p.is_symlink()
            if not selected:assert sha(p)==sha(source/sub/(name+ext))
            if bridge is not None:assert sha(p)==sha(Path(bridge)/'predictions'/sub/(name+ext))
    actual=load(folder/'decisions.json')
    assert sorted(actual['changed'])==sorted(changed)
    assert sorted(actual['records'],key=lambda x:x['ordinal'])==sorted(decisions,key=lambda x:x['ordinal'])
    costs['selected_pages']=len(changed)
    return costs
