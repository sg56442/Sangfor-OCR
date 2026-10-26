"""Finite diagnostic only; frozen Table protocol; all protocol errors fatal."""
import sys,os,json,time,fcntl,hashlib
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/experimenter'),str(R/'code/runtime'),str(R/'scripts'),str(R/'code/research')];O=Path(sys.argv[1]).resolve();GPU=sys.argv[2]
def load(p):return json.loads(Path(p).read_text())
def save(p,d):p=Path(p);t=p.with_suffix('.tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2));t.replace(p)
def gate():
 (R/'agents/shared/rsi_directives.md').read_text();load(R/'rsi_resource_directive.json')
 from empty_timegate_0074_v3 import check
 cfg=load(O/'time_binding.json');assert cfg['binding']['gpu']==GPU and cfg['binding']['out']==str(O) and Path(cfg['binding']['ledger']).resolve()==(O/'budget.json').resolve()
 end=check(R,cfg);assert (end-datetime.now(timezone.utc)).total_seconds()>120
if __name__=='__main__':
 if '--hidden' not in sys.argv:
  from empty_hidden_0074_v3 import restricted
  args=restricted(O,[sys.executable,'-B',str(Path(__file__).resolve()),str(O),GPU,'--hidden']);os.execvp(args[0],args)
 from dependency_lock_0111_v1 import verify
 verify(O/'dependencies.json');gate()
 from single_model_selective_v1 import HIDDEN
 assert all(Path(p).stat().st_size==0 for p in HIDDEN)
 lock=(R/f'control/phase2_final_gpu_locks/{GPU}.lock').open('a+')
 while True:
  gate()
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
  except BlockingIOError:time.sleep(.5)
 from phase2_runtime_guard_v1 import guard
 svc=guard(GPU);save(O/'service.json',svc);os.environ['FT1021_AUDIT_DIR']=str(O/'audit');import http_audit
 from native_wire_audit_v1 import install
 install(O/('wire_'+str(time.time_ns())));import http_budget_v1
 os.environ['FT1021_SUPPLEMENTAL_BUDGET']=str(O/'budget.json');active={}
 def reserve(path):
  with open(path,'r+') as f:
   fcntl.flock(f,fcntl.LOCK_EX);s=json.load(f);source=active['source_sha256'];owner=source+':'+str(active['owner']);ident=active['identity'];assert s['reserved']<s['maximum'] and s['sources'].get(source,0)<4 and s['owners'].get(owner,0)<1 and ident not in s['identities'];s['reserved']+=1;s['sources'][source]=s['sources'].get(source,0)+1;s['owners'][owner]=s['owners'].get(owner,0)+1;s['identities'].append(ident);f.seek(0);json.dump(s,f);f.truncate();f.flush();os.fsync(f.fileno());return s['reserved']
 http_budget_v1.reserve=reserve;http_budget_v1.install()
 from mineru_vl_utils import MinerUClient
 from finite_request_identity_0101_v1 import params,prompts
 from sparse_image_0122_support_v6 import audit_usage
 client=MinerUClient(backend='http-client',model_name=svc['model'],server_url=svc['lease']['endpoint'],max_retries=0,http_timeout=90,max_concurrency=1,use_tqdm=False,handle_equation_block=False,image_analysis=False)
 s=client.sampling_params['[default]'];actual=dict(model=svc['model'],temperature=s.temperature,top_p=s.top_p,top_k=s.top_k,presence_penalty=s.presence_penalty,frequency_penalty=s.frequency_penalty,repetition_penalty=s.repetition_penalty,vllm_xargs=dict(no_repeat_ngram_size=s.no_repeat_ngram_size,debug=False),skip_special_tokens=False)
 rows=load(O/'prepared.json');assert actual==params('text') and actual==params('text')
 for q in rows:
  assert q['parameters']==actual and q['prompt']==client.prompts['[default]']==prompts('text')[0]['text'];assert hashlib.sha256((O/f'prepared{q["ordinal"]}.bin').read_bytes()).hexdigest()==q['prepared_sha256']
 reserved_at_start=load(O/'budget.json')['reserved'];start=time.monotonic();out=load(O/'responses.json') if (O/'responses.json').exists() else [];status='FAILED'
 try:
  for active in rows:
   j=active['ordinal'];claim=O/f'claim{j}.json'
   if claim.exists():continue
   gate();verify(O/'dependencies.json');assert hashlib.sha256(Path(active['source']).read_bytes()).hexdigest()==active['source_sha256'];assert hashlib.sha256(Path(active['raw']).read_bytes()).hexdigest()==active['raw_sha256'];save(claim,dict(identity=active['identity'],retry=0));t=time.monotonic();rec=dict(ordinal=j,configured=True,triggered=True,applied=False,consumed=False,selected=False,scored=False,status='CLAIMED');out.append(rec);save(O/'responses.json',out)
   try:
    value=client._batch_predict([(O/f'prepared{j}.bin').read_bytes()],[active['prompt']],[s],None,None)[0];logs=[json.loads(x) for x in (O/'audit/http.jsonl').read_text().splitlines()];c=[x for x in logs if x['stage']=='configured'][-1];v=[x for x in logs if x['stage']=='consumed'][-1]
    assert c['parameters']==params('text') and c['prompts']==prompts('text');assert c['images'][0]['pixel_sha256']==active['pixel_sha256'];assert v['request_sha256']==c['request_sha256'] and v['response']['model']==svc['model'];assert v['response']['usage']['prompt_tokens']==active['processor']['prompt_tokens']
    rec.update(applied=True,consumed=True,status='CONSUMED',text=value.text,response=v['response'],request_sha256=c['request_sha256'],finish=v['response']['choices'][0]['finish_reason'],wall_seconds=time.monotonic()-t);save(O/'responses.json',out)
   except Exception as e:
    rec.update(status='FAILED',failure_class=type(e).__name__,error=str(e),wall_seconds=time.monotonic()-t);save(O/'responses.json',out)
  status='COMPLETE'
 finally:
  usage=audit_usage(O,out);n=load(O/'budget.json')['reserved']-reserved_at_start;save(O/'execution.json',dict(status=status,actual_HTTP=n,**usage,unknown_usage_attempts=n-usage['known_usage_attempts'],wall_seconds=time.monotonic()-start,GT_hidden=True,GPU_busy_seconds=None,retry=0));fcntl.flock(lock,fcntl.LOCK_UN)
