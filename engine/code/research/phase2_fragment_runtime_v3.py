"""Current-input shared-schema live runtime. Never reads prior answers/proposals."""
import argparse,json,hashlib,sys,os,time,shutil,re,subprocess,datetime,importlib
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/experimenter'),str(R/'code/runtime')]
from phase2_fragment_proposal_v2 import proposals
from phase2_fragment_axes_v1 import verify
from phase2_fragment_selector_v1 import select
from phase2_final_time_gate_v1 import deadline
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--pages',required=True);a.add_argument('--input',required=True);a.add_argument('--native',required=True);a.add_argument('--native-http',required=True);a.add_argument('--out',required=True);a.add_argument('--budget',type=int,default=1);a.add_argument('--permit');a.add_argument('--permit-sha256');a.add_argument('--prepare-only',action='store_true');args=a.parse_args()
 O=Path(args.out).resolve();O.mkdir(parents=True,exist_ok=False);start=time.monotonic();P=json.load(open(args.pages));B=Path(args.input).resolve();N=Path(args.native).resolve()
 deps=[Path(__file__),R/'code/research/phase2_fragment_proposal_v2.py',R/'code/research/phase2_fragment_axes_v1.py',R/'code/research/phase2_fragment_selector_v1.py',R/'code/research/phase2_fragment_processor_v2.py',R/'code/research/table_mechanisms.py',R/'code/experimenter/phase2_runtime_guard_v1.py',R/'code/experimenter/phase2_final_time_gate_v1.py',R/'code/runtime/http_audit.py',R/'code/experimenter/http_budget_v1.py']
 for name in ['mineru_vl_utils','PIL','lxml','numpy','cv2']:
  module=importlib.import_module(name);deps.extend(p for p in Path(module.__file__).parent.rglob('*') if p.is_file() and p.suffix in ['.py','.so'])
 hashes={str(p.resolve()):sha(p) for p in deps};inputs={str(Path(args.pages).resolve()):sha(args.pages),str(Path(args.native_http).resolve()):sha(args.native_http)}
 for p in P:
  for x in [B/'raw'/(p['id']+'.json'),B/'markdown'/(p['id']+'.md'),N/'raw'/(p['id']+'.json'),Path(p['image'])]:inputs[str(x.resolve())]=sha(x)
 binding=dict(input=str(B),native=str(N),pages=str(Path(args.pages).resolve()),out=str(O),budget=args.budget,inputs_sha256=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest(),closure_sha256=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest())
 end=deadline(R,__file__,binding,args.permit,args.permit_sha256)
 (O/'binding.json').write_text(json.dumps(dict(binding=binding,source_hashes=hashes,input_hashes=inputs,deadline=str(end)),indent=2))
 rows,nt,npairs=proposals(P,B);plan=[]
 for r in rows:
  if not r['eligible']:continue
  raw=json.load(open(r['raw']));native=json.load(open(N/'raw'/(r['page']+'.json')))
  if any(i>=len(native['blocks']) or native['blocks'][i]!=raw['blocks'][i] for i in r['indices']):r.update(eligible=False,reason='current_B_modified_covered_block');continue
  r['axes']=verify(r,raw)
  if not r['axes']['accept']:r.update(eligible=False,reason='source_internal_axis_unverified');continue
  n=len(plan);r['request_id']=f'fragment{n:02}';r['type']='table'
  with Image.open(r['image']) as im:
   im=im.convert('RGB');crop=im.crop(r['box']);path=O/f'view_{n}.png';crop.save(path);source=O/f'source_{n}.png';im.save(source)
  r.update(image_path=str(path),processor_source_copy=str(source),pixel_sha256=hashlib.sha256(crop.tobytes()).hexdigest());plan.append(r)
 (O/'census.json').write_text(json.dumps(dict(pages=len(P),tables=nt,pairs=npairs,eligible=len(plan),rows=rows),indent=2));(O/'plan.json').write_text(json.dumps(plan,indent=2))
 if len(plan)>args.budget:raise RuntimeError('Complete denominator exceeds budget; no requests sent')
 if args.prepare_only:return
 for sub in ['raw','markdown']:
  (O/'candidate'/sub).mkdir(parents=True)
  for p in P:shutil.copyfile(B/sub/(p['id']+('.json' if sub=='raw' else '.md')),O/'candidate'/sub/(p['id']+('.json' if sub=='raw' else '.md')))
 records=[];usage={k:0 for k in ['prompt_tokens','completion_tokens','total_tokens']};cons=[]
 if plan:
  from phase2_runtime_guard_v1 import guard
  svc=guard('3');(O/'service_binding.json').write_text(json.dumps(svc,indent=2))
  subprocess.run(['docker','exec','-e','CUDA_VISIBLE_DEVICES=',svc['lease']['container'],'python3',str(R/'code/research/phase2_fragment_processor_v2.py'),svc['processor_model_view'],str(O),str(Path(args.native_http).resolve())],check=True)
  plan=json.load(open(O/'processor_plan.json'))
  os.environ['FT1021_AUDIT_DIR']=str(O/'audit');import http_audit
  (O/'transport_budget.json').write_text(json.dumps(dict(maximum=args.budget,reserved=0,denied=0,exhausted=False)));os.environ['FT1021_SUPPLEMENTAL_BUDGET']=str(O/'transport_budget.json');from http_budget_v1 import install;install()
  from mineru_vl_utils import MinerUClient
  from mineru_vl_utils.post_process import post_process
  from mineru_vl_utils.structs import ContentBlock
  client=MinerUClient(backend='http-client',model_name=svc['model'],server_url=svc['lease']['endpoint'],handle_equation_block=False,image_analysis=False,max_retries=0,max_concurrency=1,max_connections=2,max_keepalive_connections=2,use_tqdm=False)
  for r in plan:
   if not(r['processor_admitted'] and r['all_original_HTTP_bound']):records.append(dict(page=r['page'],applied=False,reason='processor_or_native_HTTP'));continue
   assert datetime.datetime.now(datetime.timezone.utc)<end
   assert all(sha(p)==v for p,v in hashes.items())
   prompt=client.prompts['table'];assert r['native_HTTP']['prompts']==[{'type':'text','text':prompt}]
   response=client._batch_predict([Image.open(r['image_path']).convert('RGB')],[prompt],[client.sampling_params.get('table',client.sampling_params['[default]'])],None,None)[0]
   pp=post_process([ContentBlock(type='table',bbox=[0.,0.,1.,1.],angle=0,content=response.text)],simple_post_process=False,handle_equation_block=False,abandon_list=False,abandon_paratext=False)
   answer=pp[0].content if len(pp)==1 else '';raw=json.load(open(r['raw']));http=[json.loads(l) for l in (O/'audit/http.jsonl').read_text().splitlines()];cons=[q for q in http if q['stage']=='consumed'];finish=cons[-1]['response']['choices'][0]['finish_reason'];decision=select(r,raw,answer,finish=='stop');mp=O/'candidate/markdown'/(r['page']+'.md');md=mp.read_text();positions=[];cursor=0
   for i in r['indices']:
    s=raw['blocks'][i]['content'];matches=[m.start()+cursor for m in re.finditer(re.escape(s),md[cursor:])]
    if not matches or (not positions and len(matches)!=1):positions=[];break
    positions.append((matches[0],matches[0]+len(s)));cursor=positions[-1][1]
   valid=bool(positions) and all(not md[positions[k][1]:positions[k+1][0]].strip() for k in range(len(positions)-1));apply=decision['accept'] and valid
   if apply:
    mp.write_text(md[:positions[0][0]]+answer+md[positions[-1][1]:]);bs=raw['blocks'];merged=dict(bs[r['indices'][0]],type='table',bbox=r['bbox'],content=answer);raw['blocks']=[merged if i==r['indices'][0] else b for i,b in enumerate(bs) if i==r['indices'][0] or i not in r['indices']];(O/'candidate/raw'/(r['page']+'.json')).write_text(json.dumps(raw,ensure_ascii=False,indent=2))
   records.append(dict(page=r['page'],raw_answer=response.text,content=answer,decision=decision,MD_unique_contiguous=valid,applied=apply))
  usage={k:sum(q['response']['usage'][k] for q in cons) for k in usage}
 (O/'answers.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));out_hash={str(p.relative_to(O)):sha(p) for p in (O/'candidate').rglob('*') if p.is_file()}
 (O/'output_hashes.json').write_text(json.dumps(out_hash,indent=2));(O/'receipt.json').write_text(json.dumps(dict(status='COMPLETE',configured=args.budget,triggered=len(plan),consumed=len(cons),selected=sum(r.get('decision',{}).get('accept',False) for r in records),applied=sum(r['applied'] for r in records),fallback=[r for r in records if not r['applied']],usage=usage,wall_seconds=time.monotonic()-start,source_hashes=hashes),indent=2))
if __name__=='__main__':main()
