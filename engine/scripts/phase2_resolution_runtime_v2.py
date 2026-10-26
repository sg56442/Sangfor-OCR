"""Fresh, resumable fixed-resolution B candidate. No diagnostic answers or GT inputs.
preflight and run always census all supplied current pages. Processor is CPU-only.
"""
import argparse,datetime,fcntl,hashlib,json,math,os,subprocess,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(R/'code/research'),str(R/'code/experimenter'),str(R/'code/runtime')]
MODEL='/opt/p2t10/model'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
ACTIVE_ARGS=None
ACTIVE_BINDING=None

def final_binding(a):
 inputs={str(a.pages):sha(a.pages),str(a.native/'audit/http.jsonl'):sha(a.native/'audit/http.jsonl')}
 for page in load(a.pages):
  for path in [a.predictions/'raw'/(page['id']+'.json'),a.predictions/'markdown'/(page['id']+'.md'),Path(page['image'])]:
   inputs[str(path)]=sha(path)
 return dict(kind='fresh_resolution',predictions=str(a.predictions),native=str(a.native),pages=str(a.pages),out=str(a.out),gpu=a.gpu,budget=a.budget,input_hashes_sha256=digest(inputs)),inputs

def controls():
 from phase2_final_time_gate_v1 import deadline
 assert ACTIVE_ARGS is not None and ACTIVE_BINDING is not None
 end=deadline(R,__file__,ACTIVE_BINDING,ACTIVE_ARGS.final_permit,ACTIVE_ARGS.final_permit_sha256)
 d=(R/'agents/shared/rsi_directives.md').read_text();resource=load(R/'agents/shared/rsi_resource_directive.json');queue=load(R/'control/phase2_queue.json');leases=load(R/'control/gpu_leases.json')
 return dict(at=now(),directive_sha256=hashlib.sha256(d.encode()).hexdigest(),resource=resource,queue=queue,leases=leases,admission_deadline=end.isoformat(),explicit_final_permit=bool(ACTIVE_ARGS.final_permit))
def restrict(a):
 """Fail-closed Python file access guard, also installed inside processor subprocess.
 Paths here are access boundaries only; no identifiers are recognition features.
 """
 allowed=[a.out,a.predictions,a.native,a.pages]
 if a.final_permit is not None:allowed.append(a.final_permit.resolve())
 denied=[R/'code/research/runs',R/'code/experimenter/runs',R/'reports',R/'runs']
 def audit(event,args):
  if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
  p=Path(os.fsdecode(args[0])).absolute()
  if any(p==x or x in p.parents for x in allowed):return
  if p.name in ('OmniDocBench.json','references.jsonl','cc-key.md') or any(p==x or x in p.parents for x in denied):raise PermissionError('Runtime forbids diagnostic/GT/history access: '+str(p))
 sys.addaudithook(audit)
 # Negative checks must actually fail before any document processing.
 tests=[R/'code/research/runs/forbidden_probe.json',R/'reports/forbidden_probe.json',Path('/opt/p2t10/hidden/OmniDocBench.json')]
 for p in tests:
  try:open(p).close()
  except PermissionError:continue
  except FileNotFoundError:raise AssertionError('guard did not reject forbidden path')
  raise AssertionError('guard failed')
 save(a.out/'access_guard.json',dict(status='PASS',blocked_tests=[str(x) for x in tests],allowed_IO_roots=[str(x) for x in allowed],policy='No diagnostic answers, historical prediction runs or GT can be opened through Python runtime. C-level model processor dependencies restricted by explicit code path.'))
def binding_key(q):return digest(dict(parameters=q['parameters'],prompts=q['prompts'],images=[dict(pixel_sha256=i['pixel_sha256'],size=i['size'],mode=i['mode']) for i in q['images']]))
def census(a):
 from PIL import Image
 from phase2_table_resolution_candidate_0018 import prepare,glyph,smart
 http=a.native/'audit/http.jsonl';configured={};consumed=set()
 for l in http.read_text().splitlines():
  q=json.loads(l)
  if q['stage']=='configured' and q['parameters'].get('model')==MODEL and q['prompts']==[dict(type='text',text='\nTable Recognition:')]:configured[q['request_sha256']]=q
  if q['stage']=='consumed':consumed.add(q['request_sha256'])
 by={}
 for h,q in configured.items():
  if h in consumed:
   for im in q['images']:by.setdefault(im['pixel_sha256'],[]).append(q)
 rows=[];plans=[];inputs=[];pages=load(a.pages)
 for p in pages:
  # id only associates input files; it never participates in prepare/admit/choose.
  rp=a.predictions/'raw'/(p['id']+'.json');mp=a.predictions/'markdown'/(p['id']+'.md');raw=load(rp);entry=dict(raw=str(rp),raw_sha256=sha(rp),markdown=str(mp),markdown_sha256=sha(mp),source=p['image'],source_sha256=sha(p['image']));inputs.append(entry)
  tables=[(i,b) for i,b in enumerate(raw['blocks']) if b['type']=='table']
  if not tables:continue
  with Image.open(p['image']) as im:
   im=im.convert('RGB')
   for i,b in tables:
    r=dict(page_io=p['id'],index=i,**entry);prepared=prepare(im,b)
    if prepared is None:
     w,h=im.size;box=[round(v*(w if j%2==0 else h)) for j,v in enumerate(b['bbox'])];cw,ch=box[2]-box[0],box[3]-box[1]
     geometry=b.get('angle',0)==0 and min(cw,ch)>=28 and cw*ch<=400000 and max(cw,ch)/min(cw,ch)<=45
     r.update(triggered=False,reason='CC_effective_height_or_area' if geometry else 'geometry');rows.append(r);continue
    k=len(plans);native=prepared['native'];view=prepared['view'];npth=a.out/'prepared'/f'{k:04}_native.png';vpth=a.out/'prepared'/f'{k:04}_view.png';npth.parent.mkdir(exist_ok=True);native.save(npth);view.save(vpth);pix=hashlib.sha256(native.tobytes()).hexdigest();vpix=hashlib.sha256(view.tobytes()).hexdigest();matches=[q for q in by.get(pix,[]) if q['images'][0]['size']==list(native.size)]
    unique={binding_key(q):q for q in matches};q=next(iter(unique.values())) if len(unique)==1 else None
    r.update(triggered=True,reason='prepared',request_id=f'view{k:04}',native_image=str(npth),image_path=str(vpth),native_pixel_sha256=pix,pixel_sha256=vpix,box=prepared['box'],scale=prepared['scale'],native_size=list(native.size),new_size=list(view.size),native_HTTP_exact_bound=q is not None,native_HTTP=q,binding_reason='exact_actual_consumed_request' if q else 'missing_or_ambiguous_native_request',glyph_p75=glyph(native)[0]);rows.append(r);plans.append(r)
 provenance=dict(pages_sha256=sha(a.pages),native_http_sha256=sha(http),inputs=inputs,code_sha256={str(p):sha(p) for p in [Path(__file__),R/'code/experimenter/phase2_final_time_gate_v1.py',R/'code/research/phase2_table_resolution_candidate_0018.py',R/'code/research/phase2_table_resolution_legal_0018.py']})
 identity=digest(provenance);state=a.out/'identity.json'
 if state.exists():assert load(state)['input_identity']==identity,'Input/code changed; use a new output directory'
 else:save(state,dict(input_identity=identity,provenance=provenance))
 save(a.out/'census.json',dict(pages=len(pages),tables=len(rows),triggered=len(plans),rows=rows));save(a.out/'plan.json',plans)
 return plans

def processor(a):
 import torch
 from transformers import AutoProcessor
 from PIL import Image
 torch.set_num_threads(2);proc=AutoProcessor.from_pretrained(str(a.model_view),local_files_only=True);rows=load(a.out/'plan.json')
 def admit(n,c,bound):return bool(bound and n["pixel_values_sha256"]!=c["pixel_values_sha256"] and c["prompt_tokens"]+4096<=8192 and c["processed_size"][1]>n["processed_size"][1])
 for r in rows:
  pair=[]
  for key in ('native_image','image_path'):
   im=Image.open(r[key]).convert('RGB');messages=[{'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':[{'type':'image','image':im},{'type':'text','text':'\nTable Recognition:'}]}];text=proc.apply_chat_template(messages,tokenize=False,add_generation_prompt=True);t=proc(text=[text],images=[im],return_tensors='pt');g=t['image_grid_thw'][0].tolist()
   pair.append(dict(input_size=list(im.size),processed_size=[g[2]*14,g[1]*14],grid=g,visual_tokens=math.prod(g)//4,prompt_tokens=int(t['input_ids'].shape[-1]),pixel_values_sha256=hashlib.sha256(t['pixel_values'].numpy().tobytes()).hexdigest()))
  r['processor']=dict(native=pair[0],candidate=pair[1]);r['processor_admitted']=admit(*pair,True);r['admitted']=admit(*pair,r['native_HTTP_exact_bound']);r['admission_reason']='admitted' if r['admitted'] else 'native_binding' if r['processor_admitted'] else 'processor_tensor_height_or_context'
  if r['native_HTTP']:
   q=dict(r['native_HTTP']);q['images']=[dict(pixel_sha256=r['pixel_sha256'],size=r['new_size'],mode='RGB')];r['request_key']=binding_key(q)
 save(a.out/'processor_plan.json',rows)

def preflight(a):
 start=time.monotonic();census(a);c=controls();lease=c['leases'][a.gpu];assert lease['state']=='READY';view=R/f"code/runtime/model-view-{lease['endpoint'].rsplit(':',1)[1]}-{lease['container']}"
 args=['docker','exec','-e','CUDA_VISIBLE_DEVICES=','-e','OMP_NUM_THREADS=2',lease['container'],'python3',str(Path(__file__).resolve()),'--mode','processor','--predictions',str(a.predictions),'--native',str(a.native),'--pages',str(a.pages),'--out',str(a.out),'--gpu',a.gpu,'--budget',str(a.budget),'--model-view',str(view)]
 with (a.out/'processor.log').open('a') as f:subprocess.run(args,check=True,stdout=f,stderr=subprocess.STDOUT)
 rows=load(a.out/'processor_plan.json');counts=dict(status='PREFLIGHT_COMPLETE',pages=load(a.out/'census.json')['pages'],tables=load(a.out/'census.json')['tables'],triggered=len(rows),processor_admitted=sum(r['processor_admitted'] for r in rows),native_bound=sum(r['native_HTTP_exact_bound'] for r in rows),admitted=sum(r['admitted'] for r in rows),unique_requests=len({r['request_key'] for r in rows if r['admitted']}),HTTP=0,wall_seconds=time.monotonic()-start)
 save(a.out/'preflight.json',counts);print(json.dumps(counts),flush=True);return rows

def execute(a,rows):
 from PIL import Image
 from phase2_runtime_guard_v1 import guard
 from phase2_table_resolution_candidate_0018 import choose
 lock=(R/f'control/phase2_final_gpu_locks/{a.gpu}.lock').open('a+')
 while True:
  controls()
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
  except BlockingIOError:time.sleep(1)
 save(a.out/'admission_controls.json',controls());svc=guard(a.gpu);save(a.out/'service_binding.json',svc)
 os.environ['FT1021_AUDIT_DIR']=str(a.out/'audit');import http_audit
 budget=a.out/'transport_budget.json'
 if not budget.exists():save(budget,dict(maximum=a.budget,reserved=0,denied=0,exhausted=False))
 else:assert load(budget)['maximum']==a.budget
 os.environ['FT1021_SUPPLEMENTAL_BUDGET']=str(budget);from http_budget_v1 import install;install()
 from mineru_vl_utils import MinerUClient
 from mineru_vl_utils.post_process import post_process
 from mineru_vl_utils.structs import ContentBlock
 client=MinerUClient(backend='http-client',model_name=svc['model'],server_url=svc['lease']['endpoint'],handle_equation_block=False,image_analysis=False,max_retries=0,max_concurrency=1,max_connections=2,max_keepalive_connections=2,use_tqdm=False)
 ledger_path=a.out/'ledger.json';ledger=load(ledger_path) if ledger_path.exists() else {};start=time.monotonic();admitted=[r for r in rows if r['admitted']]
 for r in admitted:
  key=r['request_key']
  if key in ledger:
   if ledger[key]['state']=='INFLIGHT':ledger[key]=dict(state='UNCERTAIN_ABSTAIN',reason='Previous process interrupted; no blind resend',request_key=key);save(ledger_path,ledger)
   continue
  controls();assert sha(r['raw'])==r['raw_sha256'] and sha(r['source'])==r['source_sha256'];assert load(budget)['reserved']<a.budget
  im=Image.open(r['image_path']).convert('RGB');assert hashlib.sha256(im.tobytes()).hexdigest()==r['pixel_sha256'];prompt=client.prompts['table'];params=client.sampling_params['table'];assert r['native_HTTP']['prompts']==[dict(type='text',text=prompt)]
  ledger[key]=dict(state='INFLIGHT',request_key=key,started_at=now());save(ledger_path,ledger)
  try:
   response=client._batch_predict([im],[prompt],[params],None,None)[0];logs=[json.loads(l) for l in (a.out/'audit/http.jsonl').read_text().splitlines()];q=[v for v in logs if v['stage']=='configured'][-1];cons=[v for v in logs if v['stage']=='consumed'][-1]
   assert binding_key(q)==key and q['parameters']==r['native_HTTP']['parameters'];assert cons['request_sha256']==q['request_sha256'];assert cons['response']['usage']['prompt_tokens']==r['processor']['candidate']['prompt_tokens']
   pp=post_process([ContentBlock(type='table',bbox=[0.,0.,1.,1.],angle=0,content=response.text)],simple_post_process=False,handle_equation_block=False,abandon_list=False,abandon_paratext=False)
   ledger[key]=dict(state='COMPLETE',request_key=key,raw_answer=response.text,content=pp[0].content if len(pp)==1 else None,finish=cons['response']['choices'][0]['finish_reason'],usage=cons['response']['usage'],actual_request_sha256=q['request_sha256'],completed_at=now())
  except Exception as e:
   ledger[key]=dict(state='FAILED',request_key=key,error=repr(e),completed_at=now())
   # Parameter/input mismatch is a hard protocol violation, not a retryable model failure.
   if isinstance(e,AssertionError):save(ledger_path,ledger);raise
  save(ledger_path,ledger);print(r['request_id'],ledger[key]['state'],flush=True)
 records=[];by_page={}
 for r in admitted:by_page.setdefault(r['page_io'],[]).append(r)
 for kind in ('raw','markdown'):(a.out/'predictions'/kind).mkdir(parents=True,exist_ok=True)
 for p in load(a.pages):
  rp=a.predictions/'raw'/(p['id']+'.json');mp=a.predictions/'markdown'/(p['id']+'.md');raw=load(rp);md=mp.read_text();changed=False
  for r in by_page.get(p['id'],[]):
   entry=ledger[r['request_key']];old=raw['blocks'][r['index']]['content'];new=old;decision=dict(accepted=False,reason=entry['state'])
   if entry['state']=='COMPLETE':new,decision=choose(old,entry['content'],entry['raw_answer'],entry['finish'])
   parity=md.count(old)==1;applied=new!=old and parity
   if applied:raw['blocks'][r['index']]['content']=new;md=md.replace(old,new,1);changed=True
   records.append(dict(page_io=p['id'],index=r['index'],request_id=r['request_id'],request_key=r['request_key'],old=old,new=new,generated=entry.get('content'),decision=decision,binding=parity,applied=applied))
  (a.out/'predictions/raw'/rp.name).write_bytes((json.dumps(raw,ensure_ascii=False,indent=2)+'\n').encode() if changed else rp.read_bytes());(a.out/'predictions/markdown'/mp.name).write_bytes(md.encode() if changed else mp.read_bytes())
 save(a.out/'replay.json',records);usage={k:sum(v.get('usage',{}).get(k,0) for v in ledger.values()) for k in ('prompt_tokens','completion_tokens','total_tokens')};save(a.out/'receipt.json',dict(status='COMPLETE',input_identity=load(a.out/'identity.json')['input_identity'],native=str(a.native),predictions_input=str(a.predictions),predictions_output=str(a.out/'predictions'),admitted=len(admitted),unique_requests=len(ledger),deduplicated=len(admitted)-len(ledger),actual_HTTP=load(budget)['reserved'],completed=sum(v['state']=='COMPLETE' for v in ledger.values()),failures=sum(v['state']!='COMPLETE' for v in ledger.values()),usage=usage,retry=0,finish_counts={s:sum(v.get('finish')==s for v in ledger.values()) for s in sorted({v.get('finish','none') for v in ledger.values()})},changed_blocks=sum(r['applied'] for r in records),changed_pages=len({r['page_io'] for r in records if r['applied']}),wall_seconds_this_execute=time.monotonic()-start,model_sha256=svc['weight_sha256']))

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['preflight','processor','run'],required=True)
 for name in ('predictions','native','pages','out'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--final-permit',type=Path);p.add_argument('--final-permit-sha256');p.add_argument('--gpu',choices=['0','1','3'],required=True);p.add_argument('--budget',type=int,required=True);p.add_argument('--model-view',type=Path);a=p.parse_args()
 for name in ('predictions','native','pages','out'):setattr(a,name,getattr(a,name).resolve())
 assert 0<a.budget<=160 and a.out.is_relative_to(R)
 global ACTIVE_ARGS,ACTIVE_BINDING
 ACTIVE_ARGS=a
 if a.mode!='processor':
  ACTIVE_BINDING,input_hashes=final_binding(a)
  controls()
 a.out.mkdir(parents=True,exist_ok=True);restrict(a)
 if a.mode!='processor':
  save(a.out/'runtime_binding.json',dict(binding=ACTIVE_BINDING,input_hashes=input_hashes,final_permit_sha256=a.final_permit_sha256))
 held=(a.out/'runtime.lock').open('a+')
 if a.mode!='processor':fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if a.mode=='processor':processor(a)
 else:
  save(a.out/'start_controls.json',controls());rows=preflight(a)
  if a.mode=='run':execute(a,rows)
if __name__=='__main__':main()
