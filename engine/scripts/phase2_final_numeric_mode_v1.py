"""Bind fresh numeric observations and deterministic nested-mode cleanup."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

from phase2_final_runtime_v1 import ROOT, PYTHON, inside, load, save, sha, verify_hashes

sys.path[:0] = [str(ROOT/'code/research'), str(ROOT/'code/experimenter'), str(ROOT/'code/runtime')]
from spacing_gate_0042 import risk, grid
from spacing_geometry_0042 import bind
from spacing_apply_0046 import span
from spacing_state_0044 import audit_rows, costs
from table_transport_preflight_0038_v2 import audit_consumed
from mineru_vl_utils.post_process import simple_process
from mineru_vl_utils.structs import ContentBlock
from PIL import Image

NUMERIC = 'code/research/spacing_wrapper_0046.py'
MODE = 'scripts/phase2_nested_math_mode_v2.py'


def identity(task):
    return hashlib.sha256(json.dumps(dict(pixel=task['pixel_sha256'],prompt=task['prompt'],
                                         parameters=task['parameters']),sort_keys=True).encode()).hexdigest()


def prepare_numeric(plan, frozen):
    out = inside(plan['output'])
    return [PYTHON,'-B',NUMERIC,'prepare','--out',inside(plan['numeric_output']),
            '--inputs',out/'B_before_numeric/predictions','--manifest',inside(frozen['pages']),
            '--native-inputs',out/'native/predictions','--native-audit',out/'native/audit/http.jsonl',
            '--model',frozen['model'],'--gpu',plan['numeric_gpu'],'--budget',str(frozen['numeric_budget']),
            '--lane-plan',inside(plan['_plan_path'])]


def approve_numeric(plan, frozen):
    from spacing_admission_0046 import request
    folder = inside(plan['numeric_output'])
    assert folder.parent == ROOT/'runs'
    cfg = load(folder/'inputs.json')
    assert cfg['model'] == frozen['model'] and cfg['budget'] == frozen['numeric_budget'] == 16
    assert cfg['gpu'] == plan['numeric_gpu'] == plan['gpu']
    out = inside(plan['output'])
    assert Path(cfg['inputs']) == out/'B_before_numeric/predictions'
    assert Path(cfg['native_inputs']) == out/'native/predictions'
    assert Path(cfg['native_audit']) == out/'native/audit/http.jsonl'
    assert Path(cfg['manifest']) == inside(frozen['pages'])
    dependencies = load(folder/'dependencies.json')
    assert all(frozen['source_hashes'].get(p) == h for p,h in dependencies.items())
    verify_hashes(dependencies)
    permit = request(folder)
    assert permit['run_binding']['weight_sha256'] == frozen['weight_sha256']
    assert permit['runtime_freeze_sha256'] == plan['freeze_sha256']
    permit.update(approved=True,approved_by='RSI')
    path = folder/'final_permit.json'
    assert not path.exists()
    save(path,permit)
    return [PYTHON,'-B',NUMERIC,'run','--out',folder,'--permit',path,'--permit-sha256',sha(path)]


def verify_numeric(folder, source, native, pages, *, frozen=None, plan=None, bridge=None):
    folder,source,native,pages = map(Path,[folder,source,native,pages])
    cfg = load(folder/'inputs.json')
    assert Path(cfg['inputs']) == source and Path(cfg['manifest']) == pages
    assert Path(cfg['native_inputs']) == native/'predictions'
    assert Path(cfg['native_audit']) == native/'audit/http.jsonl'
    assert cfg['budget'] == 16 and cfg['gpu'] in ['0','1','3']
    assert cfg['model'] == '/opt/p2t10/model'
    verify_hashes(load(folder/'dependencies.json'))
    verify_hashes(load(folder/'input_binding.json'))
    if frozen is not None:
        assert all(frozen['source_hashes'].get(p) == h for p,h in load(folder/'dependencies.json').items())
        assert cfg['gpu'] == plan['numeric_gpu'] and cfg['budget'] == frozen['numeric_budget']
        from spacing_admission_0046 import request
        expected = request(folder)
        actual = load(folder/'final_permit.json')
        expected.update(approved=True,approved_by='RSI')
        assert expected == actual
    manifest = load(pages)
    assert len(manifest) == len({r['id'] for r in manifest}) == 1651
    by_id = {r['id']:r for r in manifest}
    census = load(folder/'census.json')
    expected_risks = []
    for row in manifest:
        raw_path = source/'raw'/(row['id']+'.json')
        for owner,block in enumerate(load(raw_path)['blocks']):
            if block['type'] == 'table':
                verdict = risk(block['content'])
                if verdict['eligible']:
                    expected_risks.append(dict(raw=str(raw_path),image=row['image'],owner=owner,
                                              bbox=block['bbox'],angle=block.get('angle',0),risk=verdict))
    assert census['rows'] == expected_risks and census['pages'] == 1651
    prepared = load(folder/'processor_plan.json')
    risk_pairs = {(r['raw'],r['owner']) for r in expected_risks}
    assert len({(r['raw'],r['owner']) for r in prepared}) == len(prepared)
    assert all((r['raw'],r['owner']) in risk_pairs for r in prepared)
    ledger = load(folder/'ledger.json')
    assert not ledger.get('protocol_fatal')
    tasks = {identity(t):(q,t) for q in prepared for t in q['tasks']}
    assert len(tasks) == len(prepared) and set(ledger['records']) == set(tasks)
    audit = audit_rows(folder/'audit/http.jsonl')
    configured,consumed = {},{}
    for row in audit:
        if row.get('stage') in ['configured','consumed']:
            dest = configured if row['stage']=='configured' else consumed
            assert row['request_sha256'] not in dest
            dest[row['request_sha256']] = row
    needed = {q['native_pixel_sha256'] for q in prepared}
    native_config,native_wire = {},{}
    for row in audit_rows(native/'audit/http.jsonl'):
        if row.get('stage')=='configured':
            for im in row.get('images',[]):
                if im['pixel_sha256'] in needed:
                    native_config[row['request_sha256']] = dict(pixel=im['pixel_sha256'],
                        parameters=row['parameters'],prompts=row['prompts'])
        elif row.get('stage')=='consumed' and row['request_sha256'] in native_config:
            item=native_config[row['request_sha256']]
            native_wire[item['pixel']]=dict(request_sha256=row['request_sha256'],**item)
    claims=[r for r in ledger['records'].values() if r['status']!='NOT_ADMITTED']
    assert len(claims)<=16 and len({r['owner'] for r in claims})==len(claims)
    for owner in {r['owner'].split(':')[0] for r in claims}:
        assert sum(r['owner'].split(':')[0]==owner for r in claims)<=4
    configured_keys = {}
    for request,cf in configured.items():
        matches=[key for key,(q,t) in tasks.items() if cf['images'][0]['pixel_sha256']==t['pixel_sha256']
                 and cf['parameters']==t['parameters'] and cf['prompts']==q['native_receipt']['prompts']]
        assert len(matches)==1 and matches[0] not in configured_keys
        key=matches[0];configured_keys[key]=request
        assert ledger['records'][key]['status']!='NOT_ADMITTED'
        if request in consumed:
            q,t=tasks[key]
            audit_consumed(cf,consumed[request],t,q['native_receipt']['parameters'])
            assert consumed[request]['response']['model']==cfg['model']
    assert set(consumed)<=set(configured)
    pending={};decisions=[]
    for key,(q,t) in tasks.items():
        assert sha(q['source'])==q['source_sha256'] and sha(q['raw'])==q['raw_sha256']
        assert q['native_receipt']==native_wire[q['native_pixel_sha256']]
        assert t['parameters']==q['native_receipt']['parameters'] and t['parameters']['frequency_penalty']==.005
        assert sha(folder/f'view_{q["index"]}_{t["view"]}.bin')==t['encoded_sha256']
        rec=ledger['records'][key]
        assert rec['owner']==q['source_sha256']+':'+str(q['owner'])
        if rec['status']!='COMPLETE':
            if rec['status']=='NOT_ADMITTED':assert key not in configured_keys
            continue
        request=configured_keys[key]
        assert request==rec['request_sha256'] and rec['response']==consumed[request]['response']
        response=rec['response'];assert response['choices'][0]['finish_reason']=='stop'
        assert rec['text']==response['choices'][0]['message']['content']
        name=Path(q['raw']).stem;row=by_id[name];raw=load(q['raw']);block=raw['blocks'][q['owner']]
        assert Path(row['image'])==Path(q['source'])
        old=block['content']
        new=simple_process([ContentBlock(type='table',bbox=[0,0,1,1],content=rec['text'])])[0].content
        if new==old:continue
        with Image.open(row['image']) as im:
            im=im.convert('RGB');w,h=im.size
            cropped=im.crop(tuple(v*s for v,s in zip(block['bbox'],[w,h,w,h]))).rotate(block.get('angle',0),expand=True)
            decision=bind(cropped,old,new)
        if not decision['accepted'] or grid(new) is None:continue
        item=pending.setdefault(name,dict(raw=raw,md=(source/'markdown'/(name+'.md')).read_bytes(),edits=[]))
        try:start,end,replacement=span(item['md'],old,new)
        except AssertionError:continue
        assert not any(start<e and end>s for s,e,_ in item['edits'])
        item['edits'].append((start,end,replacement));item['raw']['blocks'][q['owner']]['content']=new
        decisions.append(dict(page=name,owner=q['owner'],decision=decision))
    candidate=folder/'selector_predictions'
    for sub,ext in [('raw','json'),('markdown','md')]:
        assert {p.stem for p in (candidate/sub).glob('*.'+ext)}==set(by_id)
    for name in by_id:
        rp=candidate/'raw'/(name+'.json');mp=candidate/'markdown'/(name+'.md')
        assert rp.is_file() and mp.is_file() and not rp.is_symlink() and not mp.is_symlink()
        if name not in pending or not pending[name]['edits']:
            assert sha(rp)==sha(source/'raw'/rp.name) and sha(mp)==sha(source/'markdown'/mp.name)
        else:
            item=pending[name];md=item['md']
            for start,end,replacement in sorted(item['edits'],reverse=True):md=md[:start]+replacement+md[end:]
            assert load(rp)==item['raw'] and mp.read_bytes()==md
    cost=costs(ledger,folder/'audit/http.jsonl');assert cost==load(folder/'cost.json')
    if bridge is not None:
        for sub,ext in [('raw','json'),('markdown','md')]:
            for p in (candidate/sub).glob('*.'+ext):assert sha(p)==sha(Path(bridge)/'predictions'/sub/p.name)
    return dict(actual_attempts=len(claims),attempts_are_conservative_upper_bound=True,
                configured_HTTP=len(configured),consumed_HTTP=len(consumed),
                extra_prompt_tokens=cost['known_prompt_tokens'],extra_completion_tokens=cost['known_completion_tokens'],
                unknown_usage_attempts=len(cost['unknown_attempt_usage']),unknown_usage_responses=cost['unknown_usage_responses'],
                unknown_wall_invocations=cost['unknown_wall_invocations'],wall_seconds=cost['known_invocation_wall_seconds'],
                selected_pages=len({r['page'] for r in decisions}),selected_owners=len(decisions),
                selected=decisions,ledger_costs=cost)


def materialize_numeric(folder, destination):
    destination=Path(destination);assert not destination.exists()
    for sub,ext in [('raw','json'),('markdown','md')]:
        target=destination/'predictions'/sub;target.mkdir(parents=True)
        files=list((Path(folder)/'selector_predictions'/sub).glob('*.'+ext));assert len(files)==1651
        for p in files:assert p.is_file() and not p.is_symlink();os.link(p,target/p.name)


def verify_mode(folder, source, pages):
    module_path=ROOT/MODE
    spec=importlib.util.spec_from_file_location('numeric_tail_mode_verify',module_path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    folder,source,pages=map(Path,[folder,source,pages])
    receipt=load(folder/'receipt.json');assert receipt['pages']==1651 and receipt['HTTP']==0
    assert receipt['source_hashes'][MODE]==sha(module_path)
    changed=0
    for row in load(pages):
        name=row['id'];rp=source/'raw'/(name+'.json');mp=source/'markdown'/(name+'.md')
        expected,markdown,edits,_=module.transform(load(rp),mp.read_bytes().decode('utf-8'),None)
        out_raw=folder/'predictions/raw'/rp.name;out_md=folder/'predictions/markdown'/mp.name
        assert out_md.read_bytes()==markdown.encode('utf-8') and load(out_raw)==expected
        if not edits:assert sha(out_raw)==sha(rp) and sha(out_md)==sha(mp)
        changed+=bool(edits)
    assert receipt['changed_pages']==changed
    return dict(HTTP=0,changed_pages=changed,wall_seconds=receipt['wall_seconds'])
