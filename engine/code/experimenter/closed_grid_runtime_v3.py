"""Current-input closed-grid B step. No historical response input, no page selection."""
import os,sys,json,hashlib,shutil,time,subprocess,argparse,copy
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/experimenter'),str(R/'code/runtime'),str(R/'scripts')]
from single_model_selective_v1 import hidden,HIDDEN
from phase2_runtime_guard_v1 import MODEL,WEIGHT
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--admission',required=True);ap.add_argument('--out',required=True);ap.add_argument('--gpu',choices=['0','1','3'],default='0');ap.add_argument('--budget',type=int,default=48);ap.add_argument('--final-validation-admission');ap.add_argument('--final-validation-sha256');ap.add_argument('--check-time-only',action='store_true');ap.add_argument('--hidden',action='store_true');a=ap.parse_args()
 if not a.hidden:
  c=hidden([sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--hidden']);os.execvpe(c[0],c,dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'))
 assert all(Path(p).stat().st_size==0 for p in HIDDEN)
 from datetime import datetime,timezone
 from phase2_final_time_gate_v1 import deadline
 time_binding=dict(kind='closed_grid',input_admission_sha256=sha(a.admission),out=str(Path(a.out).resolve()),gpu=a.gpu,budget=a.budget)
 run_deadline=deadline(R,__file__,time_binding,a.final_validation_admission,a.final_validation_sha256)
 if a.check_time_only:
  print(json.dumps(dict(status='TIME_ADMISSION_PASS',deadline=run_deadline.isoformat(),model_calls=0)));return
 from PIL import Image
 from closed_grid_preflight_v1 import detect
 from closed_grid_admission_v1 import admit
 from closed_grid_selector_v1 import select
 from mineru_vl_utils.post_process import json2md
 from single_model_a_rules_v1 import serialize_markdown
 admission=load(a.admission);assert admission['model']==MODEL and admission['weight_sha256']==WEIGHT and admission['scope']=='pure_same_model_B_optional_math'
 assert 0<=a.budget<=48
 for p,h in admission['source_hashes'].items():assert sha(p)==h,p
 for p,h in admission['input_hashes'].items():assert sha(p)==h,p
 B=Path(admission['predictions']);pages=load(admission['pages']);assert len(pages)==admission['page_count']
 assert {p['id'] for p in pages}=={p.stem for p in (B/'raw').glob('*.json')}=={p.stem for p in (B/'markdown').glob('*.md')}
 O=Path(a.out).resolve();assert O.is_relative_to(R/'code/experimenter/runs');O.mkdir(exist_ok=False)
 state=dict(status='SCANNING',configured=True,GT_hidden=True,new_native_calls=0,selected=0,applied=0,scored=0,budget=a.budget,retries=0);save(O/'execution.json',state)
 start=time.monotonic();regions=[];scan=[];allblocks=0
 for page in pages:
  f=B/'raw'/f'{page["id"]}.json';raw=load(f)
  with Image.open(page['image']) as im:
   for i,b in enumerate(raw['blocks']):
    allblocks+=1
    if b['type'] not in ('text','title'):continue
    q=detect(im,raw,i);ad=admit(im,q);scan.append(dict(page=page['id'],block=i,proposal=q,admission=ad))
    if ad['admitted']:
     regions.append(dict(image=page['image'],image_sha256=sha(page['image']),raw=str(f),raw_sha256=sha(f),indices=[i],page=page['id'],unique_owner=True,complete_context=True,kind='positive',trigger_evidence=q,views=[dict(rect=q['rect'],scale=1.,task='table')]))
 save(O/'scan.json',dict(rows=scan,all_blocks=allblocks,text_title_blocks=len(scan),triggered=len(regions),wall_seconds=time.monotonic()-start))
 state.update(triggered=len(regions),scan_wall_seconds=time.monotonic()-start);save(O/'execution.json',state)
 if len(regions)>a.budget:
  state.update(status='INCOMPLETE_BUDGET_EXCEEDED',actual_calls=0);save(O/'execution.json',state);raise SystemExit(2)
 alternatives=[]
 if regions:
  plan=dict(mode='current_input_runtime',family='closed_grid_D0138',max_attempts=a.budget,regions=regions);save(O/'plan.json',plan)
  identity=dict(source_hashes=admission['source_hashes'],plan_sha256=sha(O/'plan.json'),time_binding=time_binding);save(O/'identity.json',identity)
  state['status']='OBSERVING';save(O/'execution.json',state)
  subprocess.run([sys.executable,'-B',str(R/'code/experimenter/closed_grid_transport_v3.py'),'--plan',str(O/'plan.json'),'--identity',str(O/'identity.json'),'--out',str(O/'observation'),'--gpu',a.gpu]+(['--final-validation-admission',a.final_validation_admission,'--final-validation-sha256',a.final_validation_sha256] if a.final_validation_admission else []),check=True)
  cost=load(O/'observation/actual_costs.json');alternatives=load(O/'observation/alternatives.json');assert cost['actual_attempts']==len(regions)
  if cost['failed'] or len(alternatives)!=len(regions):state.update(status='INCOMPLETE_OBSERVATION_FAILURE',cost=cost);save(O/'execution.json',state);raise SystemExit(3)
 else:cost=dict(actual_attempts=0,extra_prompt_tokens=0,extra_completion_tokens=0,failed=0,missing_usage=0,GPU_busy_seconds=None)
 changed={};selected=[]
 for reg,alt in zip(regions,alternatives):
  assert sha(reg['raw'])==alt['raw_sha256'] and sha(reg['image'])==alt['source_image_sha256'] and alt['consumed'] and alt['processor']['result']['prompt_tokens_match']
  gate=select(reg['trigger_evidence'],alt['raw_answer'],alt['finished_normally']);selected.append(dict(page=reg['page'],block=reg['indices'][0],gate=gate,response_sha256=sha(O/'observation/alternatives.json')))
  if gate['accept']:
   raw=changed.setdefault(reg['page'],load(reg['raw']));i=reg['indices'][0];raw['blocks'][i].update(type='table',content=gate['html'],merge_prev=False)
 files=[]
 for kind,ext in [('raw','json'),('markdown','md')]:
  (O/'predictions'/kind).mkdir(parents=True)
  for f in sorted((B/kind).glob('*.'+ext)):
   dst=O/'predictions'/kind/f.name
   if f.stem in changed:dst.write_text(json.dumps(changed[f.stem],ensure_ascii=False,indent=2) if kind=='raw' else serialize_markdown(json2md(changed[f.stem]['blocks']))[0])
   else:shutil.copyfile(f,dst)
   files.append(dict(path=str(dst.relative_to(O)),source_sha256=sha(f),output_sha256=sha(dst),changed=sha(f)!=sha(dst)))
 for p,h in admission['source_hashes'].items():assert sha(p)==h
 for p,h in admission['input_hashes'].items():assert sha(p)==h
 save(O/'manifest.json',dict(files=files,admission_sha256=sha(a.admission),source_hashes=admission['source_hashes'],input_hashes=admission['input_hashes']))
 save(O/'selection.json',selected);save(O/'actual_costs.json',cost)
 state.update(status='COMPLETE',pages=len(pages),consumed=len(alternatives),selected=sum(x['gate']['accept'] for x in selected),applied=sum(x['gate']['accept'] for x in selected),changed_pages=list(changed),cost=cost,wall_seconds=time.monotonic()-start,scored=0);save(O/'execution.json',state);print(json.dumps(state))
if __name__=='__main__':main()
