"""RSI final adapter for frozen0074: independent source, wire and complete output verification."""
import sys,json,hashlib,time,io,base64,html,re,collections
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'scripts'),str(R/'code/research'),str(R/'code/experimenter'),str(R/'code/runtime')]
from phase2_final_runtime_v1 import ROOT,PYTHON,inside,load,save,sha,now,verify_hashes
from empty_timegate_0074_v3 import input_hash,source_hashes,check
from empty_cell_0074_v2 import candidates
from finite_request_identity_0101_v1 import helper,pix,key,params,prompts,MODEL
from mineru_vl_utils.structs import ContentBlock
from PIL import Image
from spacing_gate_0042 import grid
from phase2_array_label_runtime_v1 import block_spans
from connective_span_0069 import paragraph_span
from repeated_runtime_0048b import patch
from lxml import html as LH
RUNNER='code/research/empty_runtime_0074_v3.py'
def image_directory(pages):
 rows=load(pages);assert len(rows)==len({x['id'] for x in rows})==1651
 dirs={str(Path(x['image']).parent) for x in rows};assert len(dirs)==1;return Path(dirs.pop())
def binding(source,pages,folder,gpu,ledger,ledger_id,dep):
 lease=load(ROOT/'control/gpu_leases.json')[gpu]
 return dict(kind='empty_cell_current_input',inputs=str(Path(source).resolve()),pages=str(image_directory(pages)),out=str(Path(folder).resolve()),gpu=str(gpu),budget=2,ledger=str(Path(ledger).resolve()),ledger_id=ledger_id,source_cap=4,owner_cap=1,retry=0,input_sha256=input_hash(source,image_directory(pages)),dependency_lock_sha256=sha(dep),service=dict(endpoint=lease['endpoint'],container_id=lease['container_id']))
def prepare(plan,frozen):
 started=time.monotonic();assert frozen['empty_runner']==RUNNER and frozen['empty_budget']==2
 out=inside(plan['output']);folder=inside(plan['empty_output']);source=inside(plan['skew_output'])/'selected_predictions';pages=inside(frozen['pages']);dep=inside(frozen['empty_dependencies']);gpu=str(plan.get('empty_gpu',plan['gpu']))
 assert folder.parent==ROOT/'runs' and not folder.exists()
 active=load(ROOT/'control/final_validation_plan.json');phase=load(ROOT/'control/phase2_plan.json')
 assert active['runtime_freeze']==plan['freeze'] and active['runtime_freeze_sha256']==plan['freeze_sha256']
 import datetime as dt
 assert dt.datetime.fromisoformat(active['start_at'])<=dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(phase['deadline_at'])
 hashes=source_hashes(ROOT);assert all(frozen['source_hashes'].get(p)==h for p,h in hashes.items())
 verify_hashes(load(dep)['files'])
 ledger=out/'empty_budget.json';permit=out/'empty_final_permit.json';assert not ledger.exists() and not permit.exists();lid=Path(plan['output']).name+'_empty'
 save(ledger,dict(ledger_id=lid,maximum=2,reserved=0,sources={},owners={},identities=[]))
 b=binding(source,pages,folder,gpu,ledger,lid,dep)
 save(permit,dict(mode='final_validation',approved=True,approved_by='RSI',phase=phase['phase'],run_binding=b,source_hashes=hashes,campaign_deadline=phase['deadline_at'],not_before=active['start_at'],active_freeze=active['runtime_freeze'],active_freeze_sha256=active['runtime_freeze_sha256']))
 cfg=dict(binding=b,permit=str(permit),permit_sha256=sha(permit),dependency_lock=str(dep),ledger=str(ledger));check(ROOT,cfg)
 save(out/'empty_prepare.json',dict(at=now(),seconds=time.monotonic()-started,binding=b,permit_sha256=sha(permit)))
 return [PYTHON,'-B',RUNNER,'--inputs',str(source),'--pages',str(image_directory(pages)),'--out',str(folder),'--gpu',gpu,'--budget','2','--ledger',str(ledger),'--dependency-lock',str(dep),'--final-validation-admission',str(permit),'--final-validation-sha256',sha(permit)]
def verify(folder,source,pages,*,plan=None,frozen=None):
 started=time.monotonic();folder,source,pages=map(lambda p:Path(p).resolve(),[folder,source,pages]);census=load(folder/'census.json');qs=load(folder/'prepared.json');answers=load(folder/'responses.json');cfg=load(folder/'time_binding.json');ledger=load(folder/'budget.json');completion=load(folder/'completion.json');execution=load(folder/'execution.json') if (folder/'execution.json').exists() else None
 offline=completion['status']=='PREPARED' and (folder/'offline_reuse.json').exists()
 witness=folder
 if offline:
  assert plan is None and frozen is None,'Offline replay forbidden for formal verification'
  reuse=load(folder/'offline_reuse.json');witness=(ROOT/reuse['from']).resolve().parent
  assert witness.is_relative_to(ROOT/'runs') and 'sealed' not in str(witness) and reuse['fresh_HTTP']==0
  assert sha(witness/'responses.json')==reuse['sha256'] and (folder/'responses.json').read_bytes()==(witness/'responses.json').read_bytes()
  oldqs={q['ordinal']:q for q in load(witness/'prepared.json')}
  for q in qs:
   for k in ['source_sha256','pixel_sha256','identity','prepared_sha256','processor','parameters','prompt','block','box']:
    assert q[k]==oldqs[q['ordinal']][k]
  assert completion['new_HTTP']==ledger['reserved']==0
  execution=load(witness/'execution.json')
 assert load(folder/'runtime_inputs.json')['inputs']==str(source)
 verify_hashes(load(folder/'dependencies.json')['files'])
 assert cfg['binding']==binding(source,pages,folder,cfg['binding']['gpu'],folder/'budget.json',ledger['ledger_id'],cfg['dependency_lock'])
 assert (completion['status']=='COMPLETE' or offline) and completion['GT_history_hidden']
 if frozen is not None:
  assert plan is not None and frozen['empty_runner']==RUNNER and frozen['empty_budget']==2
  assert folder==inside(plan['empty_output']) and source==inside(plan['skew_output'])/'selected_predictions'
  assert cfg['binding']['gpu']==str(plan.get('empty_gpu',plan['gpu'])) and Path(cfg['dependency_lock']).resolve()==inside(frozen['empty_dependencies'])
  permit=load(cfg['permit']);assert sha(cfg['permit'])==cfg['permit_sha256'] and permit['run_binding']==cfg['binding'] and permit['active_freeze_sha256']==plan['freeze_sha256']
  assert permit['source_hashes']==source_hashes(ROOT)
  assert all(frozen['source_hashes'].get(p)==h for p,h in load(folder/'dependencies.json')['files'].items())
 manifest={r['id']:r for r in load(pages)};assert len(manifest)==1651;locked={};rows=[]
 for name in sorted(manifest):
  rp=source/'raw'/(name+'.json');mp=source/'markdown'/(name+'.md');src=Path(manifest[name]['image'])
  for f in [src,rp,mp]:locked[str(f)]=sha(f)
  for i,b in enumerate(load(rp)['blocks']):
   if b['type']!='table' or '<td></td>' not in b.get('content',''):continue
   with Image.open(src) as im:cs=candidates(im,b)
   for c in cs:
    j=len(rows);crop=c.pop('crop')
    with Image.open(folder/f'cell{j}.png') as saved:assert saved.size==crop.size and saved.convert('RGB').tobytes()==crop.convert('RGB').tobytes()
    rows.append(dict(ordinal=j,source=str(src),raw=str(rp),owner=i,block=b,source_sha256=locked[str(src)],raw_sha256=locked[str(rp)],**c))
 assert census['pages']==1651 and census['bindings']==locked and census['rows']==json.loads(json.dumps(rows))
 expected=sorted(rows,key=lambda q:(q['source_sha256'],q['owner'],q['row'],q['col']))[:2];assert len(qs)<=len(expected)
 processor=None
 if qs:
  import torch
  from transformers import AutoProcessor
  torch.set_num_threads(2);processor=AutoProcessor.from_pretrained(MODEL,local_files_only=True)
 for q in qs:
  r=next(x for x in expected if x['ordinal']==q['ordinal']);assert all(q[k]==json.loads(json.dumps(v)) for k,v in r.items())
  with Image.open(folder/f'cell{q["ordinal"]}.png') as im:data,ps,_,_=helper().prepare_for_extract(im,[ContentBlock(type='text',bbox=[0,0,1,1],angle=0)])
  assert data[0]==(folder/f'prepared{q["ordinal"]}.bin').read_bytes() and sha(folder/f'prepared{q["ordinal"]}.bin')==q['prepared_sha256']
  v=Image.open(io.BytesIO(data[0]));assert pix(v)==q['pixel_sha256'] and key(v.size,pix(v),'text')==q['identity'];assert q['parameters']==params('text') and ps[0]==q['prompt']==prompts('text')[0]['text']
  msgs=[dict(role='system',content='You are a helpful assistant.'),dict(role='user',content=[dict(type='image',image=v),dict(type='text',text=ps[0])])];tensor=processor(text=[processor.apply_chat_template(msgs,tokenize=False,add_generation_prompt=True)],images=[v],return_tensors='pt');m=dict(prompt_tokens=int(tensor['input_ids'].shape[-1]),grid=tensor['image_grid_thw'].tolist(),tensor_sha256=hashlib.sha256(tensor['pixel_values'].numpy().tobytes()).hexdigest());assert m==q['processor'] and m['prompt_tokens']+4096<=8192
 actual_n=ledger['reserved'];observed_ledger=load(witness/'budget.json') if offline else ledger
 n=observed_ledger['reserved'];assert n==execution['actual_HTTP']<=2 and len(answers)==n
 if not offline:assert n==completion['new_HTTP']
 ledger=observed_ledger
 assert len(set(ledger['identities']))==len(ledger['identities'])==n and all(x<=4 for x in ledger['sources'].values()) and all(x<=1 for x in ledger['owners'].values())
 billed=[next(q for q in qs if q['ordinal']==a['ordinal']) for a in answers];assert ledger['sources']==dict(collections.Counter(q['source_sha256'] for q in billed));assert ledger['owners']==dict(collections.Counter(q['source_sha256']+':'+str(q['owner']) for q in billed));assert ledger['identities']==[q['identity'] for q in billed]
 audits=[json.loads(x) for x in (witness/'audit/http.jsonl').read_text().splitlines()] if n else [];configured={x['request_sha256']:x for x in audits if x['stage']=='configured'};consumed={x['request_sha256']:x for x in audits if x['stage']=='consumed'};wires=[]
 for p in witness.glob('wire_*/index.jsonl'):wires.extend((p.parent,json.loads(x)) for x in p.read_text().splitlines())
 tokens=dict(prompt_tokens=0,completion_tokens=0);known=0
 if n:
  service=load(witness/'service.json');assert service['read_only_checkpoint_mount'] and service['model']==MODEL and service['weight_sha256']=='01dcb5addfa1d6133fd0930e79fa2484817cb0228af21cb4917fa73d04fa3147';verify_hashes(service['processor_hashes'])
  if frozen is not None:assert service['container_id']==frozen['services'][cfg['binding']['gpu']]['container_id']
 for a,q in zip(answers,billed):
  if a['status']!='CONSUMED':assert a['status']=='FAILED';continue
  known+=1;c=configured[a['request_sha256']];v=consumed[a['request_sha256']];assert c['parameters']==params('text') and c['prompts']==prompts('text') and len(c['images'])==1 and c['images'][0]['pixel_sha256']==q['pixel_sha256'];assert v['response']==a['response']
  matches=[(p,w) for p,w in wires if w.get('response_file') and load(p/w['response_file'])==a['response']];assert len(matches)==1;p,w=matches[0];assert w['status_code']==200 and sha(p/w['request_file'])==w['request_sha256'] and sha(p/w['response_file'])==w['response_sha256'];req=load(p/w['request_file']);res=load(p/w['response_file']);assert {k:v for k,v in req.items() if k!='messages'}==params('text');images=[c['image_url']['url'] for m in req['messages'] if isinstance(m['content'],list) for c in m['content'] if c['type']=='image_url'];assert len(images)==1 and base64.b64decode(images[0].split(',',1)[1])==(folder/f'prepared{q["ordinal"]}.bin').read_bytes();texts=[c['text'] for m in req['messages'] if isinstance(m['content'],list) for c in m['content'] if c['type']=='text'];assert texts==[q['prompt']];assert a['text']==res['choices'][0]['message']['content'] and a['finish']==res['choices'][0]['finish_reason'] and res['model']==MODEL;assert res['usage']['prompt_tokens']==q['processor']['prompt_tokens']
  for k in tokens:tokens[k]+=res['usage'][k]
 if n:
  assert execution['known_usage_attempts']==known and execution['unknown_usage_attempts']==n-known
  assert all(execution[k]==v for k,v in tokens.items())
 byid={a['ordinal']:a for a in answers};edits={};decisions=[]
 for q in qs:
  a=byid.get(q['ordinal'],{});d=dict(ordinal=q['ordinal'],accepted=False);decisions.append(d)
  if a.get('status')!='CONSUMED' or a.get('finish')!='stop' or not a.get('text','').strip():d['reason']='transport_or_empty';continue
  old=q['block']['content'];g=grid(old);positions=[i for i,c in enumerate(g['cells']) if c['row']==q['row'] and c['col']==q['col']];cells=LH.fromstring(old).xpath('.//td|.//th');i=positions[0]
  if len(positions)!=1 or len(cells)!=len(g['cells']) or len(cells[i]) or (cells[i].text or '').strip():d['reason']='not_literal_empty';continue
  matches=list(re.finditer(r'<(?:td|th)\b[^>]*>.*?</(?:td|th)>',old,re.S|re.I));m=matches[i]
  if not re.fullmatch(r'<(?:td|th)\b[^>]*>\s*</(?:td|th)>',m.group(),re.I):d['reason']='markup_ambiguous';continue
  entry=m.group();at=entry.index('>')+1;payload='<br/>'.join(html.escape(z.strip()) for z in a['text'].strip().splitlines());new=old[:m.start()]+entry[:at]+payload+entry[at:]+old[m.end():];edits.setdefault(Path(q['raw']).name,[]).append((q['owner'],old,new,d));d['reason']='complete_response_literal_empty_cell'
 changed=[]
 for name in sorted(manifest):
  rp=source/'raw'/(name+'.json');mp=source/'markdown'/(name+'.md');rb=rp.read_bytes();mb=mp.read_bytes();raw=json.loads(rb);replacements=[];mdedits=[]
  for i,old,new,d in edits.get(rp.name,[]):
   try:
    assert raw['blocks'][i]['content']==old;span=paragraph_span(mb,old,new);assert not any(span[0]<e and span[1]>s for s,e,_ in mdedits);mdedits.append(span);replacements.append((*block_spans(rb,raw)[i],json.dumps(dict(raw['blocks'][i],content=new),ensure_ascii=False).encode()));d['accepted']=True
   except (AssertionError,KeyError,IndexError):d['reason']='raw_MD_binding_fallback'
  nr,nm=patch(rb,replacements),patch(mb,mdedits)
  if (nr,nm)!=(rb,mb):changed.append(name)
  for sub,p,data in [('raw',rp,nr),('markdown',mp,nm)]:
   target=folder/'selected_predictions'/sub/p.name;assert target.is_file() and not target.is_symlink() and target.read_bytes()==data
 assert decisions==load(folder/'compose.json')['decisions']
 for sub in ['raw','markdown']:assert len(list((folder/'selected_predictions'/sub).iterdir()))==1651
 result=dict(actual_attempts=actual_n,extra_prompt_tokens=0 if offline else tokens['prompt_tokens'],extra_completion_tokens=0 if offline else tokens['completion_tokens'],known_usage_attempts=0 if offline else known,unknown_usage_attempts=0 if offline else n-known,offline_observation_replay=offline,reused_observations=n if offline else 0,failed=0 if offline else n-known,missing_usage=0 if offline else n-known,retries=0,maximum_attempts=2,source_cap=4,owner_cap=1,wall_seconds=0 if offline else execution.get('wall_seconds',0),runtime_seconds=completion['wall_seconds']+completion['admission_seconds'],risk_pages=len({r['source'] for r in rows}),risk_cells=len(rows),selected_cells=sum(d['accepted'] for d in decisions),changed_pages=changed)
 return result,time.monotonic()-started
