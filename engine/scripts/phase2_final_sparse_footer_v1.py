"""Fresh, bounded sparse-image observations and source-bound table-note verification."""
import collections
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from phase2_final_runtime_v1 import ROOT,PYTHON,inside,load,save,sha,verify_hashes

SPARSE = 'code/experimenter/sparse_image_0122_v6.py'
FOOTER = 'scripts/phase2_table_math_footer_v4.py'


def sparse_command(plan, mode):
    out = inside(plan['sparse_output'])
    argv = [PYTHON,'-B',SPARSE,mode,'--out',str(out)]
    if mode == 'run':
        permit = out/'final_permit.json'
        argv += ['--final-permit',str(permit),'--final-permit-sha256',sha(permit)]
    return argv


def prepare_sparse(plan, frozen, source):
    out = inside(plan['sparse_output'])
    assert not out.exists() and out.parent == ROOT/'runs'
    pages = load(inside(frozen['pages']))
    parents = {str(Path(p['image']).parent.resolve()) for p in pages}
    assert len(parents) == 1
    started = time.monotonic()
    subprocess.run([PYTHON,'-B',SPARSE,'initialize','--inputs',str(source),
                    '--image-dir',next(iter(parents)),'--out',str(out),
                    '--gpus',str(plan['sparse_gpu']),'--cap',str(frozen['sparse_budget']),
                    '--layout-cap',str(frozen['sparse_layout_budget']),
                    '--formula-cap',str(frozen['sparse_formula_budget']),'--source-cap','6','--owner-cap','3'],
                   cwd=ROOT,check=True,capture_output=True,text=True)
    local = load(out/'input_manifest.json')
    assert {r['id']:r['image'] for r in local} == {r['id']:r['image'] for r in pages}
    subprocess.run(sparse_command(plan,'permit-request'),cwd=ROOT,check=True,capture_output=True,text=True)
    request = load(out/'permit_request.json')
    for path,digest in request['source_hashes'].items():
        assert frozen['source_hashes'].get(path) == digest, path
    control = load(ROOT/'control/final_validation_plan.json')
    assert request['final_plan_sha256'] == sha(ROOT/'control/final_validation_plan.json')
    assert request['runtime_freeze_sha256'] == plan['freeze_sha256'] == sha(inside(plan['freeze']))
    assert request['not_before'] == control['start_at']
    assert request['campaign_deadline'] == control['deadline_at']
    permit = dict(request,approved=True,approved_by='RSI')
    assert not (out/'final_permit.json').exists()
    save(out/'final_permit.json',permit)
    save(out/'initialization.json',dict(wall_seconds=time.monotonic()-started,new_HTTP=0))
    return sparse_command(plan,'run')


def materialize_sparse(folder, destination):
    folder,destination = Path(folder),Path(destination)
    assert not destination.exists()
    files = {}
    for sub,ext in [('raw','.json'),('markdown','.md')]:
        source = folder/'candidate/predictions'/sub
        paths = sorted(source.glob('*'+ext))
        assert len(paths) == 1651
        target = destination/'predictions'/sub
        target.mkdir(parents=True)
        for p in paths:
            assert p.is_file() and not p.is_symlink()
            os.link(p,target/p.name)
            files[sub+'/'+p.name] = sha(p)
    save(destination/'binding.json',dict(source=str(folder.resolve()),
         composition_sha256=sha(folder/'candidate/composition.json'),files=files,new_HTTP=0))


def verify_footer(destination, source, pages):
    import phase2_table_math_footer_v4 as rule
    from PIL import Image
    destination,source,pages = map(lambda p:Path(p).resolve(),[destination,source,pages])
    receipt = load(destination/'receipt.json')
    assert receipt['HTTP'] == receipt['tokens'] == 0 and receipt['GT_hidden'] and receipt['network_isolated']
    assert sha(destination/'pages.json') == receipt['manifest_sha256'] == sha(pages)
    verify_hashes(receipt['source_hashes'])
    manifest = {p['id']:p['image'] for p in load(pages)}
    assert receipt['pages'] == len(receipt['records']) == len(manifest) == 1651
    assert {r['id'] for r in receipt['records']} == set(manifest)
    for row in receipt['records']:
        name = row['id']
        assert row['source'] == manifest[name] and sha(row['source']) == row['source_sha256']
        raw,md = load(source/'raw'/(name+'.json')),(source/'markdown'/(name+'.md')).read_bytes().decode('utf-8')
        edits,audit = [],[]
        if any(b['type']=='table' and rule.lexical(b.get('content') or '') for b in raw['blocks']):
            with Image.open(row['source']) as image:
                raw,md,edits,audit = rule.transform(raw,md,image)
        assert json.loads(json.dumps(edits)) == row['changes']
        assert json.loads(json.dumps(audit)) == row['audit']
        assert raw == load(destination/'predictions/raw'/(name+'.json'))
        assert md.encode('utf-8') == (destination/'predictions/markdown'/(name+'.md')).read_bytes()
        for sub,ext,key in [('raw','.json','raw'),('markdown','.md','md')]:
            path = destination/'predictions'/sub/(name+ext)
            assert path.is_file() and not path.is_symlink()
            assert sha(path) == row['output_'+key+'_sha256']
            assert sha(source/sub/(name+ext)) == row['input_'+key+'_sha256']
            if not edits:
                assert row['input_'+key+'_sha256'] == row['output_'+key+'_sha256']
    assert receipt['changed_pages'] == sum(bool(r['changes']) for r in receipt['records'])
    return receipt


def verify_sparse(folder, source, pages, plan=None, frozen=None, bridge=None):
    sys.path[:0] = [str(ROOT/'code/experimenter'),str(ROOT/'code/runtime')]
    from dependency_lock_0111_v1 import verify
    from finite_request_identity_0101_v1 import prepare,pix,key,params,prompts,helper,valid_record
    from phase2_runtime_guard_v1 import MODEL,WEIGHT
    from sparse_image_0122_v6 import normalized_math
    from census_phase2_sparse_image_v1 import features
    from phase2_sparse_relation_v1 import relation_features
    from phase2_sparse_equation_gate_v1 import gate
    from PIL import Image
    folder,source,pages = map(lambda p:Path(p).resolve(),[folder,source,pages])
    verify(folder/'dependencies.json')
    cfg = load(folder/'runtime_inputs.json')
    assert Path(cfg['inputs']).resolve() == source
    manifest = {p['id']:p['image'] for p in load(pages)}
    assert {p['id']:p['image'] for p in load(folder/'input_manifest.json')} == manifest
    census = load(folder/'census.json')
    assert census['pages'] == len(census['input_bindings']) == len(manifest) == 1651
    for row in census['input_bindings']:
        assert Path(row['raw']).parent.resolve() == source/'raw'
        assert Path(row['markdown']).parent.resolve() == source/'markdown'
        for field in ['raw','markdown','source']:
            assert sha(row[field]) == row[field+'_sha256']
    binding = load(folder/'admission_binding.json')
    assert sha(folder/'census.json') == binding['census_sha256']
    assert sha(folder/'layout_plan.json') == binding['layout_plan_sha256']
    if plan is not None:
        permit = load(folder/'final_permit.json')
        assert permit['approved'] and permit['approved_by']=='RSI' and permit['run_binding']==binding
        assert permit['final_plan_sha256']==sha(ROOT/'control/final_validation_plan.json')
        assert permit['runtime_freeze_sha256']==plan['freeze_sha256']==sha(inside(plan['freeze']))
    budget = load(folder/'budget.json')
    assert budget['caps'] == binding['caps'] == cfg['caps']
    assert budget['reserved'] == len(budget['identities']) == len(set(budget['identities'])) == len(budget['attempts'])
    assert budget['reserved'] <= budget['caps']['total'] <= 48
    if frozen is not None:
        assert budget['caps'] == dict(total=frozen['sparse_budget'],layout=frozen['sparse_layout_budget'],
                                     formula=frozen['sparse_formula_budget'],source=6,owner=3)
    rebuilt={name:collections.Counter() for name in ['by_source','by_owner','by_stage','owner_layout']}
    by_identity={}
    for index,attempt in enumerate(budget['attempts'],1):
        assert attempt['number']==index and attempt['stage'] in ['layout','formula']
        assert attempt['identity'] not in by_identity
        by_identity[attempt['identity']]=attempt
        for name,counter_key in [('by_source','source'),('by_owner','owner'),('by_stage','stage')]:
            rebuilt[name][attempt[counter_key]]+=1
        if attempt['stage']=='layout':rebuilt['owner_layout'][attempt['owner']]+=1
    assert budget['identities']==list(by_identity)
    for name,count in rebuilt.items():assert dict(count)==budget[name],name
    assert all(n<=budget['caps'][stage] for stage,n in budget['by_stage'].items())
    for field,cap in [('by_source','source'),('by_owner','owner')]:
        assert all(n<=budget['caps'][cap] for n in budget[field].values())
    assert all(n<=1 for n in budget['owner_layout'].values())
    assert not list(folder.glob('protocol_failure_*.json'))
    cap_decisions={}
    for stage in ['layout','formula']:
        previous=[a for a in budget['attempts'] if stage=='formula' and a['stage']=='layout']
        total=len(previous);count=0
        sources=collections.Counter(a['source'] for a in previous)
        owners=collections.Counter(a['owner'] for a in previous)
        identities={a['identity'] for a in previous};reasons=[];caps=budget['caps']
        for q in load(folder/(stage+'_plan.json'))['requests']:
            c=census['records'][q['ordinal']];source_key=c['source_sha256']
            owner_key=source_key+':'+str(c['owner']);k=q['identity_key'];reason=None
            if k in identities:reason='duplicate_effective_request'
            elif total>=caps['total']:reason='global_cap'
            elif count>=caps[stage]:reason='stage_cap'
            elif sources[source_key]>=caps['source']:reason='source_cap'
            elif owners[owner_key]>=caps['owner']:reason='owner_cap'
            reasons.append(reason)
            if reason is None:
                total+=1;count+=1;sources[source_key]+=1;owners[owner_key]+=1;identities.add(k)
        cap_decisions[stage]=reasons
    costs = dict(actual_attempts=0,extra_prompt_tokens=0,extra_completion_tokens=0,failed=0,
                 non_stop_decodes=0,worker_seconds_sum=0.0,unknown_usage_attempts=0,
                 interrupted_invocations_unknown_wall=0,orphan_consumed_responses=0)
    observations = []
    for worker in sorted(folder.glob('gpu*_*')):
        if not worker.is_dir():
            continue
        execution,cost,service = map(load,[worker/'execution.json',worker/'cost.json',worker/'service.json'])
        assert execution['status'] in ['COMPLETE','COMPLETE_WITH_FAILURES']
        assert execution['GT_hidden'] and execution['retry']==0
        assert service['model']==MODEL and service['weight_sha256']==WEIGHT and service['read_only_checkpoint_mount']
        gpu = worker.name.split('_')[0][3:]
        stage=worker.name.split('_')[1]
        requests=load(folder/(stage+'_plan.json'))['requests']
        lane=list(map(str,cfg['gpus'])).index(gpu)
        claims={}
        for index,q in enumerate(requests):
            if index%len(cfg['gpus'])!=lane:continue
            claim=folder/'requests'/(q['identity_key']+'.claim.json')
            if claim.exists():
                c=load(claim)
                if c==dict(gpu=gpu,request=index,stage=stage):claims[q['identity_key']]=index
        if frozen is not None:
            assert service['container_id']==frozen['services'][gpu]['container_id']
        assert load(worker/'dependency_preHTTP.json')['lock_sha256']==sha(folder/'dependencies.json')
        records = load(worker/'results.json') if (worker/'results.json').exists() else []
        auditpath = worker/'audit/http.jsonl'
        audit = [json.loads(s) for s in auditpath.read_text().splitlines()] if auditpath.exists() else []
        configured = {r['request_sha256']:r for r in audit if r['stage']=='configured'}
        consumed = {r['request_sha256']:r['response'] for r in audit if r['stage']=='consumed'}
        assert len(consumed)==sum(r['stage']=='consumed' for r in audit)
        wire = {}
        for path in worker.glob('wire/**/index.jsonl'):
            for line in path.read_text().splitlines():
                row = json.loads(line)
                req,resp = path.parent/row['request_file'],path.parent/row['response_file']
                assert sha(req)==row['request_sha256'] and sha(resp)==row['response_sha256']
                if row['status_code']==200:
                    digest=hashlib.sha256(json.dumps(load(req),sort_keys=True).encode()).hexdigest()
                    wire[digest]=load(resp)
        attempts = load(worker/'attempts.json') if (worker/'attempts.json').exists() else []
        expected_attempts=[r['number'] for r in budget['attempts']
                           if r['stage']==stage and r['identity'] in claims]
        assert sorted(attempts)==expected_attempts and len(attempts)==len(set(attempts))
        assert cost['actual_HTTP']==len(attempts)
        costs['actual_attempts']+=len(attempts)
        costs['worker_seconds_sum']+=cost['wall_seconds']
        costs['failed']+=cost['failed']
        assert cost['failed']==sum(r.get('status','').startswith('FAILED') for r in records)
        if 'invocation_count' in cost:
            invocations=[load(p) for p in (worker/'invocations').iterdir() if p.is_file()]
            assert len(invocations)==cost['invocation_count']
            assert sum(r.get('wall_seconds',0) for r in invocations)==cost['wall_seconds']
            assert sum(r.get('status')=='RUNNING' for r in invocations)==cost['interrupted_invocations_unknown_wall']
            costs['interrupted_invocations_unknown_wall']+=cost['interrupted_invocations_unknown_wall']
        for label in ['prompt_tokens','completion_tokens']:
            actual=sum(r.get('usage',{}).get(label,0) for r in consumed.values())
            assert actual==cost[label]
            costs['extra_'+label]+=actual
        known_usage=sum(bool(r.get('usage')) for r in consumed.values())
        assert known_usage<=len(attempts)
        if 'known_usage_attempts' in cost:
            assert cost['known_usage_attempts']==known_usage
            assert cost['unknown_usage_attempts']==len(attempts)-known_usage
        costs['unknown_usage_attempts']+=len(attempts)-known_usage
        attached={r['request_sha256'] for r in records if r.get('consumed')}
        costs['orphan_consumed_responses']+=len(set(consumed)-attached)
        assert len({r['request'] for r in records})==len(records)
        verified_wire=set()
        for r in records:
            index=r['request'];q=requests[index]
            assert index%len(cfg['gpus'])==lane
            assert all(r[k]==v for k,v in q.items())
            k=r['identity_key'];charged=k in by_identity and claims.get(k)==index
            if charged:
                c=census['records'][r['ordinal']];a=by_identity[k]
                assert a['source']==c['source_sha256'] and a['owner']==c['source_sha256']+':'+str(c['owner'])
                assert a['stage']==stage
            if not r.get('consumed'):
                assert not r.get('response') and not r.get('raw_answer')
                assert r['status'] in ['NOT_ADMITTED','CLAIMED_NO_RETRY','FAILED_TRANSPORT']
                if r['status']=='NOT_ADMITTED':
                    assert not charged and claims.get(k)!=index and not r.get('applied')
                    assert r['reason'] in ['global_cap','stage_cap','source_cap','owner_cap','duplicate_effective_request','deadline_margin']
                    if r['reason']=='deadline_margin':
                        remaining=(dt.datetime.fromisoformat(r['deadline'])-dt.datetime.fromisoformat(r['checked_at'])).total_seconds()
                        assert abs(remaining-r['remaining_seconds'])<1e-5 and remaining<=120
                    else:assert r['reason']==cap_decisions[stage][index]
                elif r['status']=='CLAIMED_NO_RETRY':
                    assert claims.get(k)==index and not r.get('applied')
                else:
                    assert charged and r.get('applied') and r.get('error')
                continue
            assert r['status']=='CONSUMED' and charged and r.get('applied')
            c=census['records'][r['ordinal']]
            assert r['raw_sha256']==c['raw_sha256'] and r['source_sha256']==c['source_sha256']
            with Image.open(c['source']) as image:
                image=image.convert('RGB')
                feature=features(image.crop(c['rect']))
                assert feature==c['features'] and feature['eligible']
                assert relation_features(image.crop(c['rect']),feature)==c['relation'] and c['relation']['eligible']
                prepared=prepare(image.crop(r['rect']),r['task'])
            assert r['identity_key']==key(prepared.size,pix(prepared),r['task'])
            qq=configured[r['request_sha256']]
            assert qq['parameters']==params(r['task'])==r['configured_parameters']
            assert qq['prompts']==prompts(r['task'])==r['configured_prompts']
            assert qq['images'][0]['pixel_sha256']==pix(prepared)
            assert wire[r['request_sha256']]==consumed[r['request_sha256']]==r['response']
            assert r['response']['model']==MODEL and r['response']['choices'][0]['message']['content']==r['raw_answer']
            assert r['processor']['result']['prompt_tokens_match']
            costs['non_stop_decodes']+=not r['finished_normally']
            verified_wire.add(r['request_sha256'])
        # Validate all attempted request audits, including orphan responses after interruption.
        for digest,qq in configured.items():
            if digest in verified_wire:continue
            matches=[]
            for index,q in enumerate(requests):
                if q['identity_key'] not in claims or claims[q['identity_key']]!=index:continue
                prepared_path=worker/(str(index)+'_prepared.png')
                if not prepared_path.exists():continue
                with Image.open(prepared_path) as prepared:
                    if pix(prepared.convert('RGB'))==qq['images'][0]['pixel_sha256']:matches.append(q)
            assert len(matches)==1
            q=matches[0];c=census['records'][q['ordinal']]
            assert qq['parameters']==params(q['task']) and qq['prompts']==prompts(q['task'])
            with Image.open(c['source']) as original:prepared=prepare(original.convert('RGB').crop(q['rect']),q['task'])
            assert pix(prepared)==qq['images'][0]['pixel_sha256']
            assert key(prepared.size,pix(prepared),q['task'])==q['identity_key']
            if digest in consumed:
                assert wire[digest]==consumed[digest] and consumed[digest]['model']==MODEL
        observations.extend(records)
    assert costs['actual_attempts']==budget['reserved']
    planned=sum([load(folder/(stage+'_plan.json'))['requests'] for stage in ['layout','formula']],[])
    identity=lambda r:(r['task'],r['ordinal'],r['identity_key'],r.get('leaf_index',-1))
    assert sorted(map(identity,observations))==sorted(map(identity,planned))
    layouts={r['ordinal']:r for r in observations if r['task']=='[layout]'}
    edits=collections.defaultdict(list)
    for r in [r for r in observations if r['task']=='equation']:
        if not valid_record(r) or not r.get('finished_normally'):
            continue
        c=census['records'][r['ordinal']]
        assert sha(folder/'layout_observations.json')==r['layout_observations_sha256']
        leaf=helper().parse_layout_output(layouts[c['ordinal']]['raw_answer'])[r['leaf_index']]
        raw=load(c['raw'])
        with Image.open(c['source']) as image:
            image=image.convert('RGB')
            rect,why=gate(image,c['rect'],leaf,raw['blocks'],c['owner'])
            assert rect==r['rect'] and why==r['source_gate']
            bbox=[v/(image.width if i%2==0 else image.height) for i,v in enumerate(rect)]
        content=normalized_math(r['raw_answer'])
        md=(source/'markdown'/(c['page']+'.md')).read_bytes()
        anchor=next(((i,b['content']) for i,b in enumerate(raw['blocks']) if i>c['owner']
                    and len(b.get('content')or'')>5 and md.count(b['content'].encode())==1),None)
        if content is None or anchor is None:
            continue
        if any(min(e['rect'][2],rect[2])>max(e['rect'][0],rect[0]) and min(e['rect'][3],rect[3])>max(e['rect'][1],rect[1]) for e in edits[c['page']]):
            continue
        edits[c['page']].append(dict(owner=c['owner'],leaf_index=r['leaf_index'],ordinal=c['ordinal'],
            rect=rect,bbox=bbox,content=content,anchor=anchor[1],anchor_index=anchor[0]))
    composition=load(folder/'candidate/composition.json')
    normalize=lambda d:{k:sorted(v,key=lambda r:(r['owner'],r['rect'][1],r['rect'][0])) for k,v in d.items()}
    assert normalize(edits)==normalize(composition['edits'])
    target=folder/'candidate/predictions'
    for sub,ext in [('raw','.json'),('markdown','.md')]:
        assert {p.stem for p in (target/sub).glob('*'+ext)}==set(manifest)
    for name in manifest:
        raw=copy.deepcopy(load(source/'raw'/(name+'.json')))
        md=(source/'markdown'/(name+'.md')).read_bytes()
        rows=edits.get(name,[])
        blocks=[]
        for i,b in enumerate(raw['blocks']):
            blocks.append(b)
            for row in sorted((r for r in rows if r['owner']==i),key=lambda r:(r['rect'][1],r['rect'][0])):
                blocks.append(dict(type='equation',bbox=row['bbox'],angle=0,content=row['content'],
                    source_image_parent_index=i,source_relation='complete_separated_equation_inside_preserved_image'))
        raw['blocks']=blocks
        groups=collections.defaultdict(list)
        for row in sorted(rows,key=lambda r:(r['owner'],r['rect'][1],r['rect'][0])):
            groups[row['anchor'].encode()].append(row['content'].encode())
        inserts=sorted([(md.index(anchor),b'\n\n'.join(parts)+b'\n\n') for anchor,parts in groups.items()],reverse=True)
        for position,data in inserts:
            md=md[:position]+data+md[position:]
        assert raw==load(target/'raw'/(name+'.json')) and md==(target/'markdown'/(name+'.md')).read_bytes()
        for sub,ext in [('raw','.json'),('markdown','.md')]:
            p=target/sub/(name+ext)
            assert p.is_file() and not p.is_symlink() and sha(p)==composition['outputs'][sub+'/'+p.name]
            if not rows:
                assert sha(p)==sha(source/sub/p.name)
            if bridge is not None:
                assert sha(p)==sha(Path(bridge)/'predictions'/sub/p.name)
    assert sorted(composition['changed_pages'])==sorted(edits)
    costs.update(selected_blocks=sum(map(len,edits.values())),selected_pages=len(edits))
    return costs
