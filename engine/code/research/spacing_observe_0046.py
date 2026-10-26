import json,sys,os,fcntl,time,hashlib,datetime
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/experimenter'),str(R/'code/runtime'),str(R/'code/research')];O=Path(os.environ['SPACING_OUT'])
from spacing_state_0044 import *
from phase2_runtime_guard_v1 import guard
from spacing_admission_0046 import admitted,wait_lock,transport_failure
permit=os.environ.get("SPACING_PERMIT") or None;permit_sha=os.environ.get("SPACING_PERMIT_SHA") or None
from table_transport_preflight_0038_v2 import audit_consumed
cfg=load(O/'inputs.json');lk=(O/'worker.lock').open('a+');fcntl.flock(lk,fcntl.LOCK_EX|fcntl.LOCK_NB)
for p,h in load(O/'dependencies.json').items():assert sha(p)==h,('dependency mismatch',p)
for p,h in load(O/'input_binding.json').items():assert sha(p)==h,('input mismatch',p)
if permit:admitted(O,permit,permit_sha)
statepath=O/'ledger.json';state=load(statepath) if statepath.exists() else dict(records={},invocations=[])
assert not state.get('protocol_fatal'), 'protocol-fatal run cannot resume'
abandon(state);start=time.monotonic();inv=dict(started_at=now(),status='RUNNING',wall_seconds=None);state['invocations'].append(inv);save(statepath,state)
# Persistent budget supports zero-call output and resume even with exhausted budget.
rows=load(O/'processor_plan.json');audit=O/'audit/http.jsonl';client=None;svc=None;s=None
try:
 for q in rows:
  for t in q['tasks']:
   key=hashlib.sha256(json.dumps(dict(pixel=t['pixel_sha256'],prompt=t['prompt'],parameters=t['parameters']),sort_keys=True).encode()).hexdigest();owner=q['source_sha256']+':'+str(q['owner'])
   if key in state['records']:continue
   if sum(r['status']!='NOT_ADMITTED' for r in state['records'].values())>=cfg['budget']:
    claim(state,key,owner,cfg['budget']);save(statepath,state);continue
   (R/'agents/shared/rsi_directives.md').read_text();load(R/'rsi_resource_directive.json');load(R/'control/gpu_leases.json')
   end=admitted(O,permit,permit_sha)
   if sum(r.get('owner','').split(':')[0]==q['source_sha256'] and r['status']!='NOT_ADMITTED' for r in state['records'].values())>=4:
    state['records'][key]=dict(owner=owner,status='NOT_ADMITTED',reason='source_cap',wall_seconds=0,usage=None);save(statepath,state);continue
   if client is None:
    gpu=str(cfg['gpu']);gl=wait_lock(R/f'control/phase2_final_gpu_locks/{gpu}.lock',end);admitted(O,permit,permit_sha);svc=guard(gpu);save(O/'service.json',svc)
    os.environ['FT1021_AUDIT_DIR']=str(O/'audit');import http_audit
    # Audit only: our fsynced ledger is the sole reservation owner.
    from mineru_vl_utils import MinerUClient
    client=MinerUClient(backend='http-client',model_name=svc['model'],server_url=svc['lease']['endpoint'],handle_equation_block=False,image_analysis=False,max_retries=0,max_concurrency=1,max_connections=2,max_keepalive_connections=2,use_tqdm=False);s=client.sampling_params['table']
   actual=dict(model=svc['model'],temperature=s.temperature,top_p=s.top_p,top_k=s.top_k,presence_penalty=s.presence_penalty,frequency_penalty=s.frequency_penalty,repetition_penalty=s.repetition_penalty,vllm_xargs=dict(no_repeat_ngram_size=s.no_repeat_ngram_size,debug=False),skip_special_tokens=False)
   assert actual==t['parameters']==q['native_receipt']['parameters'];assert [dict(type='text',text=t['prompt'])]==q['native_receipt']['prompts'];assert client.prompts['table']==t['prompt'];assert sha(q['source'])==q['source_sha256'];assert sha(q['raw'])==q['raw_sha256'];data=(O/f'view_{q["index"]}_{t["view"]}.bin').read_bytes();assert hashlib.sha256(data).hexdigest()==t['encoded_sha256']
   admitted(O,permit,permit_sha)
   assert claim(state,key,owner,cfg['budget']);rec=state['records'][key];rec.update(index=q['index'],view=t['view'],audit_start=len(audit_rows(audit)));save(statepath,state) # fsync BEFORE transport
   clock=time.monotonic()
   try:response=client._batch_predict([data],[t['prompt']],[s],None,None)[0]
   except BaseException as e:
    rec.update(status='TRANSPORT_FAILED_UNKNOWN_USAGE',error_type=type(e).__name__,wall_seconds=time.monotonic()-clock);save(statepath,state)
    try:ordinary=transport_failure(e,audit_rows(audit)[rec['audit_start']:],t,q['native_receipt'],svc['model'])
    except BaseException:
     rec['status']='PROTOCOL_FATAL';state['protocol_fatal']=True;save(statepath,state);raise
    if ordinary:
     consumed=[x for x in audit_rows(audit)[rec['audit_start']:] if x.get('stage')=='consumed']
     if consumed:
      rs=consumed[-1];rec.update(request_sha256=rs['request_sha256'],usage=rs['response'].get('usage'))
      if rs['response']['choices'][0]['finish_reason']!='stop':rec['status']='INCOMPLETE_FALLBACK'
     save(statepath,state);continue
    rec['status']='PROTOCOL_FATAL';state['protocol_fatal']=True;save(statepath,state);raise
   try:
    logs=audit_rows(audit)[rec['audit_start']:];cf=[v for v in logs if v['stage']=='configured'][-1];rs=[v for v in logs if v['stage']=='consumed'][-1]
    rec.update(request_sha256=cf['request_sha256'],usage=rs['response'].get('usage'),wall_seconds=time.monotonic()-clock)
    audit_consumed(cf,rs,t,q['native_receipt']['parameters']);assert cf['prompts']==q['native_receipt']['prompts'];assert rs['response']['model']==svc['model'];assert rs['request_sha256']==cf['request_sha256']
   except BaseException:
    rec['status']='PROTOCOL_FATAL';state['protocol_fatal']=True;save(statepath,state);raise
   rec['status']='COMPLETE' if rs['response']['choices'][0]['finish_reason']=='stop' else 'INCOMPLETE_FALLBACK';rec['response']=rs['response'];rec['text']=response.text;save(statepath,state);print(rec['status'],q['index'],flush=True)
 inv['status']='COMPLETE'
except BaseException:
 inv['status']='FAILED';raise
finally:
 inv['wall_seconds']=time.monotonic()-start;inv['ended_at']=now();save(statepath,state);save(O/'cost.json',costs(state,audit))
