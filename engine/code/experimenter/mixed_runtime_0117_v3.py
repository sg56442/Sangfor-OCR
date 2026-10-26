"""Frozen mixed-context candidate. Arbitrary manifest/current predictions; no GT/old responses."""
import argparse,json,hashlib,sys,os,time,fcntl,io,copy,shutil
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/experimenter'),str(R/'code/runtime'),str(R/'scripts'),str(R/'code/research')]
from mixed_context_0115_v1 import triggered,context
from mixed_anchor_0115_v2 import select

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def save(p,v):
 p=Path(p);t=p.with_suffix('.tmp');t.write_text(json.dumps(v,ensure_ascii=False,indent=2));t.replace(p)
def scan(inputs,manifest):
 records=[];fingerprints=[];pages=load(manifest)
 for p in pages:
  raw=inputs/'raw'/(p['id']+'.json');d=load(raw);fingerprints.append([p['id'],sha(raw)])
  for i,b in enumerate(d['blocks']):
   if not triggered(b):continue
   c=context(d['blocks'],i);records.append(dict(raw=str(raw),raw_sha256=sha(raw),page=p['id'],source=p['image'],source_sha256=sha(p['image']),target=i,context=c,configured=True,triggered=True,applied=False,consumed=False,selected=False,scored=False,reason='eligible' if c else 'ambiguous_geometry'))
 return dict(pages=len(pages),records=records,input_digest=hashlib.sha256(json.dumps(fingerprints).encode()).hexdigest(),manifest_sha256=sha(manifest))
ADMISSION=None
def deadline():
 from mixed_admission_0117_v3 import admitted
 out,permit,permit_sha,final_mode=ADMISSION
 end=admitted(R,out,permit,permit_sha,final_mode)
 assert (end-datetime.now(timezone.utc)).total_seconds()>120,'Insufficient request deadline margin'
 (R/'agents/shared/rsi_directives.md').read_text();(R/'rsi_resource_directive.json').read_text()
 return end

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--manifest',required=True);ap.add_argument('--out',required=True);ap.add_argument('--mode',choices=['scan','init','run','compose'],required=True);ap.add_argument('--gpu',choices=['0','1','3'],default='1');ap.add_argument('--budget',type=int,default=16);ap.add_argument('--hidden',action='store_true');ap.add_argument('--track',choices=['A','B'],default='B');ap.add_argument('--final-mode',action='store_true');ap.add_argument('--final-permit');ap.add_argument('--final-permit-sha256');a=ap.parse_args();I=Path(a.inputs).resolve();M=Path(a.manifest).resolve();O=Path(a.out).resolve();assert O.is_relative_to(R) and 0<=a.budget<=16;O.mkdir(parents=True,exist_ok=True)
 global ADMISSION
 ADMISSION=(O,a.final_permit,a.final_permit_sha256,a.final_mode)
 if a.mode=='run' and a.track=='A':
  save(O/'A_network_denied.json',dict(HTTP=0,reason='Track A prohibits model calls'));raise SystemExit('Track A network disabled')
 if a.mode=='run' and not a.hidden:
  from panel_hidden_0110_v2 import restricted
  c=restricted(O,[sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--hidden']);os.execvp(c[0],c)
 if a.mode in ['scan','init']:
  if a.mode=='init' and not (O/'binding.json').exists():assert not (O/'responses.json').exists() and not (O/'audit').exists(),'Fresh init forbids historical responses'
  t=time.monotonic();s=scan(I,M);s['CPU_scan_seconds']=time.monotonic()-t;save(O/'census.json',s)
  if a.mode=='init':
   binding=dict(inputs=str(I),manifest=str(M),out=str(O),budget=a.budget,input_digest=s['input_digest'],manifest_sha256=s['manifest_sha256'])
   if (O/'binding.json').exists():assert load(O/'binding.json')==binding
   else:save(O/'binding.json',binding)
   save(O/'runtime_inputs.json',dict(inputs=str(I)))
   from dependency_lock_0111_v1 import create
   if not (O/'dependencies.json').exists():create(O/'dependencies.json',['code/experimenter/mixed_runtime_0117_v3.py','scripts/launch_owned.py'])
   from mixed_admission_0117_v3 import binding as make_binding
   admission=make_binding(I,M,O,a.budget,a.gpu,a.track)
   if (O/'admission_binding.json').exists():assert load(O/'admission_binding.json')==admission
   else:save(O/'admission_binding.json',admission)
   save(O/'permit_request.json',dict(run_binding=admission,source_hashes=load(O/'dependencies.json')['files'],instruction='RSI must supply approval, phase, not_before, campaign_deadline, final_plan_sha256, runtime_freeze absolute path and hash; this is not an approval'))
   if not (O/'budget.json').exists():save(O/'budget.json',dict(maximum=a.budget,reserved=0,by_source={},owners=[]))
  print(json.dumps(dict(pages=s['pages'],risk=len(s['records']),eligible=sum(x['context'] is not None for x in s['records']))));return
 from dependency_lock_0111_v1 import verify
 verify(O/'dependencies.json')
 from mixed_admission_0117_v3 import binding as make_binding
 assert make_binding(I,M,O,a.budget,a.gpu,a.track)==load(O/'admission_binding.json'),'Complete input/admission binding mismatch'
 if a.final_mode or a.final_permit:deadline()
 binding=load(O/'binding.json');assert binding['inputs']==str(I) and binding['manifest']==str(M) and binding['budget']==a.budget
 current=scan(I,M);assert current['input_digest']==binding['input_digest'] and current['manifest_sha256']==binding['manifest_sha256']
 if a.mode=='compose':
  from mixed_compose_0117_v3 import compose_page
  D=O/'candidate';changed=[]
  for kind in ['raw','markdown']:
   (D/kind).mkdir(parents=True,exist_ok=True)
   for p in (I/kind).iterdir():
    q=D/kind/p.name
    if not q.exists():shutil.copyfile(p,q)
    assert not q.is_symlink(),'Output must be materialized'
  receipts=load(O/'responses.json') if a.track=='B' and (O/'responses.json').exists() else [];decisions=[];groups={}
  for r in receipts:
   assert r['admission_sha256']==sha(O/'admission_binding.json'),'Response belongs to another run'
   q=current['records'][r['ordinal']]
   groups.setdefault(q['page'],[]).append((r['ordinal'],q['target'],q['context']['indices'],r))
  for page,items in groups.items():
   raw=load(I/'raw'/(page+'.json'));md=(I/'markdown'/(page+'.md')).read_bytes()
   value,text,ds=compose_page(raw,md,items);decisions.extend(dict(page=page,**d) for d in ds)
   if any(d['selected'] for d in ds):
    save(D/'raw'/(page+'.json'),value);(D/'markdown'/(page+'.md')).write_bytes(text);changed.append(page)
  save(O/'decisions.json',dict(records=decisions,changed=changed));print(json.dumps(dict(changed=len(changed))));return
 from PIL import Image
 from finite_request_identity_0101_v1 import helper,pix,key,MODEL
 from mineru_vl_utils.structs import ContentBlock
 from transformers import AutoProcessor
 import torch
 from phase2_runtime_guard_v1 import guard
 from mineru_vl_utils import MinerUClient
 from single_model_selective_v1 import HIDDEN
 assert all(Path(p).stat().st_size==0 for p in HIDDEN)
 responses=load(O/'responses.json') if (O/'responses.json').exists() else [];done={r['ordinal'] for r in responses if r.get('admission_sha256')==sha(O/'admission_binding.json')};assert len(done)==len(responses),'Foreign response directory';todo=[(j,q) for j,q in enumerate(current['records']) if q['context'] and j not in done]
 deadline()
 if not todo:save(O/'resume.json',dict(new_HTTP=0,completed=len(done),empty_domain=not current['records']));return
 deadline();torch.set_num_threads(2);proc=AutoProcessor.from_pretrained(MODEL,local_files_only=True);h=helper();prepared=[]
 for j,q in todo:
  im=Image.open(q['source']).convert('RGB');b=q['context']['bbox'];box=[round(b[0]*im.width),round(b[1]*im.height),round(b[2]*im.width),round(b[3]*im.height)];crop=im.crop(box);data,ps,params,_=h.prepare_for_extract(crop,[ContentBlock(type='text',bbox=[0.,0.,1.,1.],angle=0)]);pim=Image.open(io.BytesIO(data[0])).convert('RGB');pim.save(O/f'prepared{j}.png');(O/f'prepared{j}.bin').write_bytes(data[0]);crop.save(O/f'source{j}.png')
  text=proc.apply_chat_template([{'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':[{'type':'image','image':pim},{'type':'text','text':ps[0]}]}],tokenize=False,add_generation_prompt=True);v=proc(text=[text],images=[pim],return_tensors='pt');assert v['input_ids'].shape[-1]+4096<=8192
  prepared.append(dict(ordinal=j,source_sha256=q['source_sha256'],owner=str(q['context']['bbox']),box=box,affine=[1,0,box[0],0,1,box[1]],prepared_to_source=[crop.width/pim.width,0,box[0],0,crop.height/pim.height,box[1]],prepared_size=list(pim.size),pixel_sha256=pix(pim),identity=key(pim.size,pix(pim),'text'),encoded_sha256=sha(O/f'prepared{j}.bin'),prompt=ps[0],grid=v['image_grid_thw'].tolist(),prompt_tokens=v['input_ids'].shape[-1],processor_tensor_sha256=hashlib.sha256(v['pixel_values'].numpy().tobytes()).hexdigest()))
 save(O/'prepared.json',prepared);lock=(R/f'control/phase2_final_gpu_locks/{a.gpu}.lock').open('a+')
 while True:
  deadline()
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
  except BlockingIOError:time.sleep(.5)
 deadline();verify(O/'dependencies.json');svc=guard(a.gpu);save(O/'service.json',svc);os.environ['FT1021_AUDIT_DIR']=str(O/'audit');import http_audit
 from native_wire_audit_v1 import install as wire
 wire(O/('wire_'+str(len(done))));os.environ['FT1021_SUPPLEMENTAL_BUDGET']=str(O/'budget.json');import http_budget_v1
 active={}
 def reserve(path):
  with open(path,'r+') as f:
   fcntl.flock(f,fcntl.LOCK_EX);s=json.load(f);source=active['source_sha256'];owner=[source,active['owner']]
   assert s['reserved']<s['maximum'] and s['by_source'].get(source,0)<2 and owner not in s['owners'],'cost/owner duplicate cap'
   s['reserved']+=1;s['by_source'][source]=s['by_source'].get(source,0)+1;s['owners'].append(owner);f.seek(0);json.dump(s,f);f.truncate();f.flush();os.fsync(f.fileno())
 http_budget_v1.reserve=reserve;http_budget_v1.install();client=MinerUClient(backend='http-client',model_name=svc['model'],server_url=svc['lease']['endpoint'],max_retries=0,http_timeout=90,max_concurrency=1,max_connections=2,max_keepalive_connections=2,use_tqdm=False,handle_equation_block=False,image_analysis=False);start=time.monotonic()
 for active in prepared:
  deadline();j=active['ordinal'];q=current['records'][j];assert sha(q['source'])==q['source_sha256'] and sha(q['raw'])==q['raw_sha256'];t=time.monotonic();rec=dict(ordinal=j,admission_sha256=sha(O/'admission_binding.json'),configured=True,triggered=True,applied=False,consumed=False,selected=False,scored=False)
  try:
   r=client._batch_predict([(O/f'prepared{j}.bin').read_bytes()],[active['prompt']],[client.sampling_params.get('text',client.sampling_params['[default]'])],None,None)[0];log=[json.loads(l) for l in (O/'audit/http.jsonl').read_text().splitlines()];resp=[x for x in log if x['stage']=='consumed'][-1];assert resp['response']['usage']['prompt_tokens']==active['prompt_tokens'];rec.update(applied=True,consumed=True,text=r.text,finish=resp['response']['choices'][0]['finish_reason'],usage=resp['response']['usage'],request_sha256=resp['request_sha256'])
  except Exception as e:rec['error']=repr(e)
  rec['wall_seconds']=time.monotonic()-t;responses.append(rec);save(O/'responses.json',responses)
 fcntl.flock(lock,fcntl.LOCK_UN);save(O/'execution.json',dict(status='COMPLETE',HTTP=load(O/'budget.json')['reserved'],worker_inference_wall=time.monotonic()-start,blind_retries=0))
if __name__=='__main__':main()
