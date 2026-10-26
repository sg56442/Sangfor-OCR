"""Finite source-bound equation children of fresh same-model local layout; retry0."""
import os,sys,json,hashlib,time,io,fcntl,subprocess,select,argparse,math
from pathlib import Path
from datetime import datetime,timezone
from PIL import Image
import httpx
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/experimenter'),str(R/'code/runtime'),str(R/'code/research'),str(R/'scripts')]
from single_model_selective_v1 import hidden,HIDDEN
from finite_request_identity_0101_v1 import prepare,pix,key,params,prompts
from phase2_runtime_guard_v1 import guard
from mineru_vl_utils import MinerUClient
from census_phase2_sparse_image_v1 import features
from phase2_sparse_equation_gate_v1 import gate
from phase2_sparse_relation_v1 import relation_features
from finite_request_identity_0101_v1 import helper
O=None
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
 p=Path(p);t=p.with_suffix('.tmp');t.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');t.replace(p)
def main():
 global O
 ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--stage',choices=['layout','formula'],required=True);ap.add_argument('--lane-index',type=int,default=0);ap.add_argument('--lane-count',type=int,default=1);ap.add_argument('--final-permit');ap.add_argument('--final-permit-sha256');ap.add_argument('--gpu',choices=['0','1','3'],required=True);ap.add_argument('--hidden',action='store_true');ap.add_argument('--attempt',default='1');ap.add_argument('--plan',default='plan.json');a=ap.parse_args();O=Path(a.out).resolve()
 if not a.hidden:
  from panel_hidden_0110_v2 import restricted
  c=restricted(O,[sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--hidden']);os.execvp(c[0],c)
 assert all(Path(p).stat().st_size==0 for p in HIDDEN)
 D=O/('gpu'+a.gpu+'_'+a.stage);D.mkdir(exist_ok=True)
 assert a.attempt=='1', 'Retry is disabled'
 from panel_admission_0112_v2 import wait_lock
 from phase2_final_time_gate_v1 import deadline
 def admitted_deadline(root,out,permit,permit_sha):
  from sparse_image_0122_support_v6 import admitted
  return admitted(out,permit,permit_sha)
 bound=load(O/'admission_binding.json')
 assert a.lane_count==len(bound['gpus']) and 0<=a.lane_index<a.lane_count and bound['gpus'][a.lane_index]==int(a.gpu),'Worker lane differs from permit binding'
 end=admitted_deadline(R,O,a.final_permit,a.final_permit_sha256)
 lock=wait_lock(R/'control/phase2_final_gpu_locks'/f'{a.gpu}.lock',end)
 end=admitted_deadline(R,O,a.final_permit,a.final_permit_sha256)
 save(D/'lock_admission.json',dict(deadline=end.isoformat(),gpu=a.gpu,lane_index=a.lane_index,lane_count=a.lane_count,only_observer_holds_lock=True))
 resources=load(R/'rsi_resource_directive.json');directives=(R/'agents/shared/rsi_directives.md').read_text();queue=load(R/'control/phase2_queue.json')
 assert (a.final_permit or queue[a.gpu]['owner']=='experimenter' or queue[a.gpu].get('shared_with')) and int(a.gpu) in resources['allowed_gpus']
 assert (end-datetime.now(timezone.utc)).total_seconds()>120,'insufficient finite batch deadline margin'
 save(D/'admission.json',dict(resources=resources,queue=queue[a.gpu],directives_sha256=hashlib.sha256(directives.encode()).hexdigest()))
 from dependency_lock_0111_v1 import verify
 frozen=verify(O/'dependencies.json');save(D/'dependency_preHTTP.json',dict(lock_sha256=sha(O/'dependencies.json'),files=len(frozen['files']),verified_at=datetime.now(timezone.utc).isoformat()))
 binding=guard(a.gpu);save(D/'service.json',binding);lease=binding['lease']
 assert a.plan==a.stage+'_plan.json', 'Fixed stage plan only'
 assert load(O/'preflight.json')['status']=='PASS'
 os.environ['FT1021_SUPPLEMENTAL_BUDGET']=str(O/'budget.json')
 import http_budget_v1;http_budget_v1.install();attempts=[];current={}
 from sparse_image_0122_support_v6 import reconciled_attempts,audit_usage
 attempts=reconciled_attempts(O,a.stage,a.gpu,a.lane_index,a.lane_count);save(D/'attempts.json',attempts)
 def reserve(path):
  from sparse_image_0122_support_v6 import reserve as atomic
  n=atomic(path,current['source'],current['identity'],current['owner_key'],current['task']);attempts.append(n);save(D/'attempts.json',attempts);return n
 http_budget_v1.reserve=reserve
 os.environ['FT1021_AUDIT_DIR']=str(D/'audit');import http_audit
 from native_wire_audit_v1 import install;install(D/'wire')
 client=MinerUClient(backend='http-client',model_name=binding['model'],server_url=lease['endpoint'],handle_equation_block=False,image_analysis=False,max_concurrency=1,max_connections=2,max_keepalive_connections=2,use_tqdm=False,max_retries=0)
 worker=None;records=load(D/'results.json') if (D/'results.json').exists() else [];start=time.monotonic();status='RUNNING';save(D/'execution.json',dict(status=status))
 invocation=D/'invocations'/str(time.time_ns());invocation.parent.mkdir(exist_ok=True);save(invocation,dict(status='RUNNING',started_at=datetime.now(timezone.utc).isoformat()))
 def receive():
  assert select.select([worker.stdout],[],[],90)[0],'processor timeout';return json.loads(worker.stdout.readline())
 try:
  census=load(O/'census.json')['records']
  from sparse_image_0122_support_v6 import planned_admission
  cap_decisions=planned_admission(O,a.stage)
  for j,q in enumerate(load(O/a.plan)['requests']):
   if j%a.lane_count!=a.lane_index:continue
   if any(r.get('request')==j for r in records):continue
   if cap_decisions[j]:
    records.append(dict(**q,request=j,status='NOT_ADMITTED',reason=cap_decisions[j],configured=True,triggered=True,applied=False,consumed=False,selected=False,scored=False));save(D/'results.json',records);continue
   checked_at=datetime.now(timezone.utc);remaining_seconds=(end-checked_at).total_seconds()
   if remaining_seconds<=120:
    records.append(dict(**q,request=j,configured=True,triggered=True,applied=False,consumed=False,selected=False,scored=False,status='NOT_ADMITTED',reason='deadline_margin',checked_at=checked_at.isoformat(),deadline=end.isoformat(),remaining_seconds=remaining_seconds));save(D/'results.json',records);continue
   c=census[q['ordinal']];assert sha(c['raw'])==c['raw_sha256'] and sha(c['source'])==c['source_sha256']
   im=Image.open(c['source']).convert('RGB');parent=load(c['raw'])['blocks'][c['owner']]
   assert parent['type']=='image' and not parent.get('content') and parent['bbox']==c['bbox']
   assert [round(v*(im.width if i%2==0 else im.height)) for i,v in enumerate(parent['bbox'])]==c['rect']
   assert features(im.crop(c['rect']))==c['features'] and c['features']['eligible']
   assert relation_features(im.crop(c['rect']),c['features'])==c['relation'] and c['relation']['eligible']
   if a.stage=='layout':
    assert q['task']=='[layout]' and q['rect']==c['rect']
   else:
    assert q['task']=='equation', 'Only locally observed equation children'
    lp=O/'layout_observations.json';assert sha(lp)==q['layout_observations_sha256']
    observations=[x for x in load(lp) if x['ordinal']==q['ordinal']]
    assert len(observations)==1 and observations[0]['status']=='CONSUMED' and observations[0]['finished_normally']
    leaf=helper().parse_layout_output(observations[0]['raw_answer'])[q['leaf_index']]
    actual,decision=gate(im,c['rect'],leaf,load(c['raw'])['blocks'],c['owner'])
    assert actual==q['rect'] and decision==q['source_gate'], 'Source or layout binding changed'
   task=q['task'];view=im.crop(q['rect']);prepared=prepare(view,task);k=key(prepared.size,pix(prepared),task);assert k==q['identity_key']
   current.update(source=c['source_sha256'],identity=k,owner_key=c['source_sha256']+':'+str(c['owner']),task=task)
   claim=O/'requests'/(k+'.claim.json');claim.parent.mkdir(exist_ok=True)
   if claim.exists():
    if not any(r.get('request')==j for r in records):
     records.append(dict(**q,request=j,status='CLAIMED_NO_RETRY',configured=True,triggered=True,applied=False,consumed=False,selected=False,scored=False));save(D/'results.json',records)
    continue
   with claim.open('x') as f:json.dump(dict(gpu=a.gpu,request=j,stage=a.stage),f)
   prepared.save(D/f'{j}_prepared.png');view.save(D/f'{j}_source.png')
   pw,ph=view.size;w,h=view.size
   if task!='[layout]' and max(w,h)/min(w,h)>client.helper.max_image_edge_ratio:
    if w>h:ph=math.ceil(w/client.helper.max_image_edge_ratio)
    else:pw=math.ceil(h/client.helper.max_image_edge_ratio)
   ox,oy=int((pw-w)/2),int((ph-h)/2);sx,sy=prepared.width/pw,prepared.height/ph
   rec=dict(**q,request=j,configured=True,triggered=True,applied=True,consumed=False,selected=False,scored=False,affine_prepared_to_source=[1/sx,0,q['rect'][0]-ox,0,1/sy,q['rect'][1]-oy],source_sha256=c['source_sha256'],raw_sha256=c['raw_sha256']);records.append(rec);t=time.monotonic()
   try:
    end=admitted_deadline(R,O,a.final_permit,a.final_permit_sha256)
    assert (end-datetime.now(timezone.utc)).total_seconds()>120, 'Stopped before HTTP'
    assert not list(O.glob('protocol_failure_*.json')), 'Another lane failed protocol verification'
    prompt=client.prompts.get(task) or client.prompts['[default]']
    sampling=client.sampling_params.get(task) or client.sampling_params['[default]']
    expected=params(task)
    assert [{'type':'text','text':prompt}]==prompts(task)
    for field in ['temperature','top_p','top_k','presence_penalty','frequency_penalty','repetition_penalty']:
     assert getattr(sampling,field)==expected[field], 'Pretransport native parameter mismatch: '+field
    assert sampling.no_repeat_ngram_size==expected['vllm_xargs']['no_repeat_ngram_size']
    audit=D/'audit/http.jsonl';before=len(audit.read_text().splitlines()) if audit.exists() else 0
    buf=io.BytesIO();prepared.save(buf,format='PNG')
    answer=client._batch_predict([buf.getvalue()],[client.prompts.get(task) or client.prompts['[default]']],[client.sampling_params.get(task) or client.sampling_params['[default]']],None,None)
    lines=[json.loads(l) for l in audit.read_text().splitlines()[before:]];qq=[x for x in lines if x['stage']=='configured'];rr=[x for x in lines if x['stage']=='consumed'];assert len(qq)==len(rr)==1;qq,rr=qq[0],rr[0]
    assert qq['parameters']==params(task) and qq['prompts']==prompts(task) and qq['images'][0]['pixel_sha256']==pix(prepared)
    assert qq['request_sha256']==rr['request_sha256'] and rr['response']['model']==binding['model']
    rec.update(consumed=True,raw_answer=answer[0].text,configured_parameters=qq['parameters'],configured_prompts=qq['prompts'],response=rr['response'],request_sha256=qq['request_sha256'],finished_normally=all(x['finish_reason']=='stop' for x in rr['response']['choices']))
    if worker is None:
     worker=subprocess.Popen(['docker','exec','-i','-e','CUDA_VISIBLE_DEVICES=','-e','OMP_NUM_THREADS=2',lease['container'],'python3','-B','-u',str(R/'scripts/processor_replay_stream_v1.py'),'--model',binding['processor_model_view'],'--root',str(D)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(D/'processor.log').open('w'),text=True,bufsize=1)
     ready=receive();assert ready['status']=='READY';save(D/'processor_owned.json',dict(container_id=binding['container_id'],client_pid=worker.pid,start_ticks=Path(f'/proc/{worker.pid}/stat').read_text().split(') ',1)[1].split()[19],worker=ready))
    worker.stdin.write(json.dumps(dict(audit=str(D/'audit'),request_sha256=qq['request_sha256']))+'\n');worker.stdin.flush();p=receive();assert p['status']=='COMPLETE' and p['result']['prompt_tokens_match'];rec['processor']=p;rec['status']='CONSUMED'
   except AssertionError as e:
    rec.update(status='FAILED_PROTOCOL',error=repr(e),wall_seconds=time.monotonic()-t);save(D/'results.json',records);save(O/('protocol_failure_'+a.gpu+'.json'),dict(stage=a.stage,error=repr(e)));raise
   except httpx.HTTPError as e:rec.update(status='FAILED_TRANSPORT',error=repr(e))
   except Exception as e:
    rec.update(status='FAILED_PROTOCOL',error=repr(e),wall_seconds=time.monotonic()-t);save(D/'results.json',records);save(O/('protocol_failure_'+a.gpu+'.json'),dict(stage=a.stage,error=repr(e)));raise
   rec['wall_seconds']=time.monotonic()-t;save(D/'results.json',records)
  status='COMPLETE' if all(r['status']=='CONSUMED' for r in records) else 'COMPLETE_WITH_FAILURES'
 except BaseException:
  status='FAILED';raise
 finally:
  if worker is not None:
   worker.stdin.write('{"stop":true}\n');worker.stdin.flush();worker.stdin.close();worker.wait(timeout=30)
  attempts=reconciled_attempts(O,a.stage,a.gpu,a.lane_index,a.lane_count);save(D/'attempts.json',attempts)
  usage=audit_usage(D,records)
  assert usage['known_usage_attempts']<=len(attempts), 'Usage without reserved transport'
  save(invocation,dict(status=status,wall_seconds=time.monotonic()-start,ended_at=datetime.now(timezone.utc).isoformat()))
  history=[load(p) for p in invocation.parent.iterdir() if p.is_file()]
  save(D/'cost.json',dict(actual_HTTP=len(attempts),**usage,unknown_usage_attempts=len(attempts)-usage['known_usage_attempts'],wall_seconds=sum(h.get('wall_seconds',0) for h in history),invocation_count=len(history),interrupted_invocations_unknown_wall=sum(h.get('status')=='RUNNING' for h in history),GPU_busy_seconds=None,failed=sum(r.get('status','').startswith('FAILED') for r in records)))
  save(D/'execution.json',dict(status=status,GT_hidden=True,retry=0,processor_exitcode=None if worker is None else worker.returncode))
if __name__=='__main__':
 try:main()
 except BaseException as e:
  if O is not None and O.is_dir():save(O/('protocol_failure_worker_'+str(os.getpid())+'.json'),dict(error=repr(e),scope='fatal source/admission/protocol/processor or worker failure; no further queue admission'))
  raise
