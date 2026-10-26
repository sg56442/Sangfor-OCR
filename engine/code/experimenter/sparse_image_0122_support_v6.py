"""Admission and atomic attempt accounting for sparse-image0122, retry zero."""
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
from dependency_lock_0111_v1 import sha, verify
from panel_admission_0112_v2 import input_digest
from phase2_final_time_gate_v1 import deadline
ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT/'code/experimenter/sparse_image_0122_v6.py'
def load(p): return json.loads(Path(p).read_text())
def save(p, data):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.tmp'); tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n'); tmp.replace(p)
def check_binding(out):
    out=Path(out); b=load(out/'admission_binding.json')
    assert b['out']==str(out.resolve())
    cfg=load(out/'runtime_inputs.json'); budget=load(out/'budget.json')
    assert cfg['inputs']==b['inputs'] and cfg['gpus']==b['gpus']
    assert cfg['caps']==b['caps']==budget['caps'], 'Budget/config binding changed'
    assert input_digest(b['inputs'])==b['inputs_sha256'], 'Current input changed'
    assert sha(out/'input_manifest.json')==b['manifest_sha256']
    assert sha(out/'census.json')==b['census_sha256']
    assert sha(out/'layout_plan.json')==b['layout_plan_sha256']
    for p,h in b['source_hashes'].items(): assert sha(p)==h, 'Source changed'
    frozen=verify(out/'dependencies.json')
    for name in ['sparse_image_0122_v6.py','sparse_image_0122_support_v6.py','sparse_image_0122_worker_v6.py']:
        path=ROOT/'code/experimenter'/name
        assert frozen['files'].get(str(path))==sha(path), 'Active entry absent from dependency lock'
    return b

def admitted(out, permit=None, permit_sha=None):
    out=Path(out); b=check_binding(out)
    frozen=verify(out/'dependencies.json')
    if permit:
        assert permit_sha and sha(permit)==permit_sha, 'Wrong permit SHA'
        p=load(permit); plan=ROOT/'control/final_validation_plan.json'; f=load(plan)
        freeze=(ROOT/f['runtime_freeze']).resolve()
        assert p['final_plan_sha256']==sha(plan)
        assert p['runtime_freeze']==str(freeze) and p['runtime_freeze_sha256']==sha(freeze)==f['runtime_freeze_sha256']
        assert all(p['source_hashes'].get(k)==v for k,v in frozen['files'].items())
    return deadline(ROOT,ENTRY,b,permit,permit_sha)

def reserve(path, source, identity, owner, task):
    """Charge every attempted wire before transport. Distinct leaves may share owner."""
    with open(path,'r+') as f:
        fcntl.flock(f,fcntl.LOCK_EX); s=json.load(f); stage='layout' if task=='[layout]' else 'formula'
        cap=s['caps']; reason=None
        if identity in s['identities']: reason='duplicate_effective_request'
        elif s['reserved']>=cap['total']: reason='global_cap'
        elif s['by_stage'].get(stage,0)>=cap[stage]: reason='stage_cap'
        elif s['by_source'].get(source,0)>=cap['source']: reason='source_cap'
        elif s['by_owner'].get(owner,0)>=cap['owner']: reason='owner_cap'
        elif stage=='layout' and s['owner_layout'].get(owner,0): reason='owner_layout_cap'
        if reason:
            s['denials'].append(dict(reason=reason,source=source,identity=identity,owner=owner,stage=stage))
        else:
            s['reserved']+=1; s['identities'].append(identity)
            for field,key in [('by_source',source),('by_owner',owner),('by_stage',stage)]:s[field][key]=s[field].get(key,0)+1
            if stage=='layout':s['owner_layout'][owner]=1
            s['attempts'].append(dict(number=s['reserved'],source=source,owner=owner,identity=identity,stage=stage,at=dt.datetime.now(dt.timezone.utc).isoformat()))
        f.seek(0);json.dump(s,f);f.truncate();f.flush();os.fsync(f.fileno())
        if reason:raise RuntimeError(reason)
        return s['reserved']


def planned_admission(out,stage):
    """Deterministic cap fallback, independent of lane completion order."""
    out=Path(out); ledger=load(out/'budget.json'); caps=load(out/'admission_binding.json')['caps']
    assert ledger['caps']==caps
    records=load(out/'census.json')['records']; total=0; sources={};owners={};identities=set()
    for a in ledger['attempts']:
        if a['stage']==stage:continue
        total+=1;sources[a['source']]=sources.get(a['source'],0)+1;owners[a['owner']]=owners.get(a['owner'],0)+1;identities.add(a['identity'])
    decisions=[];stage_count=0
    for q in load(out/(stage+'_plan.json'))['requests']:
        c=records[q['ordinal']];source=c['source_sha256'];owner=source+':'+str(c['owner']);identity=q['identity_key'];reason=None
        if identity in identities:reason='duplicate_effective_request'
        elif total>=caps['total']:reason='global_cap'
        elif stage_count>=caps[stage]:reason='stage_cap'
        elif sources.get(source,0)>=caps['source']:reason='source_cap'
        elif owners.get(owner,0)>=caps['owner']:reason='owner_cap'
        decisions.append(reason)
        if reason is None:
            total+=1;stage_count+=1;sources[source]=sources.get(source,0)+1;owners[owner]=owners.get(owner,0)+1;identities.add(identity)
    return decisions


def reconciled_attempts(out,stage,gpu,lane,count):
    out=Path(out);plan=load(out/(stage+'_plan.json'))['requests'];numbers=[]
    with (out/'budget.json').open() as f:
        fcntl.flock(f,fcntl.LOCK_SH);ledger=json.load(f)
    census=load(out/'census.json')['records']
    for attempt in ledger['attempts']:
        if attempt['stage']!=stage:continue
        claim=load(out/'requests'/(attempt['identity']+'.claim.json'))
        assert claim['stage']==stage
        q=plan[claim['request']];c=census[q['ordinal']]
        assert q['identity_key']==attempt['identity'] and c['source_sha256']==attempt['source']
        assert attempt['owner']==c['source_sha256']+':'+str(c['owner'])
        if str(claim['gpu'])==str(gpu):
            assert claim['request']%count==lane
            numbers.append(attempt['number'])
    return sorted(numbers)

def audit_usage(worker,records):
    worker=Path(worker);responses={}
    path=worker/'audit/http.jsonl'
    if path.exists():
        for line in path.read_text().splitlines():
            row=json.loads(line)
            if row['stage']=='consumed':
                key=row['request_sha256'];prior=responses.setdefault(key,row['response'])
                assert prior==row['response'], 'Conflicting consumed audit responses'
    for row in records:
        if row.get('response') and row.get('request_sha256'):
            assert row['request_sha256'] in responses, 'Record response missing consumed audit'
            prior=responses[row['request_sha256']]
            assert prior==row['response'], 'Conflicting audit/record response'
    usages=[v['usage'] for v in responses.values() if v.get('usage')]
    return dict(prompt_tokens=sum(u.get('prompt_tokens',0) for u in usages),completion_tokens=sum(u.get('completion_tokens',0) for u in usages),known_usage_attempts=len(usages))
