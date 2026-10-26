"""Bounded current-input prose recovery; full risk recomputed; no diagnostic routes/responses."""
import argparse,json,sys,os,time,hashlib,subprocess,io,math
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/experimenter'),str(R/'scripts')]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,j):Path(p).write_text(json.dumps(j,ensure_ascii=False,indent=2))
def main():
 ap=argparse.ArgumentParser()
 for name in ['inputs','pages','out','gpu']:ap.add_argument('--'+name,required=True)
 ap.add_argument('--max-plan-rows',type=int,default=0);ap.add_argument('--budget',type=int,default=32);ap.add_argument('--ledger');ap.add_argument('--max-new-http',type=int,default=32);ap.add_argument('--prepare-only',action='store_true');ap.add_argument('--hidden',action='store_true');ap.add_argument('--check-time-only',action='store_true');ap.add_argument('--final-validation-admission');ap.add_argument('--final-validation-sha256');a=ap.parse_args();assert a.gpu in ['0','1','3'] and 0<=a.budget<=32
 base=Path(a.inputs).resolve();O=Path(a.out).resolve();assert O.parent==R/'runs';pages=Path(a.pages).resolve();images={p.stem:p for p in pages.iterdir() if p.is_file()};files=sorted((base/'raw').glob('*.json'));assert len(files)==1651
 binding=dict(max_plan_rows=a.max_plan_rows,kind='prose_current_input',inputs=str(base),pages=str(pages),out=str(O),gpu=a.gpu,budget=a.budget,ledger=a.ledger,max_new_http=a.max_new_http,input_sha256=hashlib.sha256(json.dumps([(p.name,sha(p),sha(base/'markdown'/(p.stem+'.md')),sha(images[p.stem])) for p in files]).encode()).hexdigest())
 from phase2_final_time_gate_v1 import deadline
 end=deadline(R,__file__,binding,a.final_validation_admission,a.final_validation_sha256)
 if a.check_time_only:print(json.dumps(dict(status='TIME_PASS',binding=binding,HTTP=0)));return
 if not a.hidden:
  if O.exists():
   prior=json.loads((O/'admission.json').read_text());assert prior['binding']==binding and prior['entry']==__file__,'Existing output admission mismatch'
   done=json.loads((O/'completion.json').read_text());assert done['status'] in ['COMPLETE','PREPARED'];print(json.dumps(dict(idempotent_existing_completion=done,HTTP=0)));return
  O.mkdir();save(O/'runtime_inputs.json',dict(inputs=str(base)));save(O/'admission.json',dict(binding=binding,entry=__file__,permit=a.final_validation_admission,permit_sha256=a.final_validation_sha256))
  from dependency_lock_0111_v1 import create
  create(O/'dependencies.json',['code/experimenter/prose_runtime_0145_v1.py','code/experimenter/prose_transport_0143_v1.py','scripts/phase2_uncovered_parallel_census_v1.py'])
  from panel_hidden_0110_v2 import restricted
  cmd=restricted(O,[sys.executable,'-B',__file__,*sys.argv[1:],'--hidden']);os.execvp(cmd[0],cmd)
 from dependency_lock_0111_v1 import verify
 verify(O/'dependencies.json')
 from single_model_selective_v1 import HIDDEN
 assert all(Path(p).stat().st_size==0 for p in HIDDEN)
 ledger=Path(a.ledger).resolve() if a.ledger else O/'budget_ledger.json'
 if not ledger.exists():save(ledger,dict(maximum=a.budget,reserved=0,sources={},owners={},identities=[],events=[]))
 state=json.loads(ledger.read_text());assert state['maximum']==a.budget;initial=state['reserved'];os.environ['FT1021_PROSE_LEDGER']=str(ledger)
 t=time.monotonic();C=O/'census';C.mkdir();subprocess.run([sys.executable,'-B',str(R/'scripts/phase2_uncovered_parallel_census_v1.py'),'--inputs',str(base),'--pages',str(pages),'--out',str(C),'--workers','3','--hidden'],check=True)
 from PIL import Image
 from prose_geometry_0143_v1 import union,intersection,parse,proposals
 from prose_expand_0142_v1 import expand
 rows=json.loads((C/'census.json').read_text())['rows'];plan=[]
 for row in rows:
  if not row['groups']:continue
  raw=json.loads(Path(row['raw']).read_bytes());im=Image.open(row['source']).convert('RGB');w,h=im.size;b=union([v for g in row['groups'] for v in g]);b=[b[0]/w,b[1]/h,b[2]/w,b[3]/h]
  if any(v['type']=='table' and intersection(b,v['bbox'])>0 for v in raw['blocks']):plan.append(dict(**row,decision='table_fallback'));continue
  for _ in raw['blocks']:
   new=union([b]+[v['bbox'] for v in raw['blocks'] if intersection(b,v['bbox'])>0])
   if new==b:break
   b=new
  b,proof=expand(im,b,raw['blocks']);plan.append(dict(**row,decision='ready',source_bbox=b,expansion=proof))
 save(O/'plan.json',plan);prepare_seconds=time.monotonic()-t
 if a.prepare_only:save(O/'completion.json',dict(status='PREPARED',HTTP=0,prepare_seconds=prepare_seconds));return
 import torch
 torch.set_num_threads(2)
 from finite_request_identity_0101_v1 import helper,pix,key,MODEL,params,prompts
 from mineru_vl_utils.structs import ContentBlock
 from transformers import AutoProcessor
 proc=AutoProcessor.from_pretrained(MODEL,local_files_only=True)
 from boxed_diagram_0133_v1 import view
 from prose_select_0143_v1 import edit
 from prose_order_resolve_0145_v1 import resolve
 outcomes=[];changes={};seq=0
 def call(row,box,task,owner):
  nonlocal seq
  state=json.loads(ledger.read_text());src=row['source_sha256'];okey=src+':'+owner
  if state['reserved']>=state['maximum'] or state['reserved']-initial>=a.max_new_http or state['sources'].get(src,0)>=4 or state['owners'].get(okey,0)>=2:return None,dict(reason='budget_cap_fallback')
  im=Image.open(row['source']).convert('RGB');c=view(im,dict(type='image',bbox=box,angle=0));rect=c['rect'];crop=im.crop(rect)
  data=helper().prepare_for_layout(crop) if task=='[layout]' else helper().prepare_for_extract(crop,[ContentBlock(type='text',bbox=[0.,0.,1.,1.],angle=0)])[0][0]
  pim=Image.open(io.BytesIO(data)).convert('RGB');identity=key(pim.size,pix(pim),task)
  if identity in state['identities']:return None,dict(reason='previous_effective_identity_fallback')
  S=O/f'stage{seq}';seq+=1;S.mkdir();crop.save(S/'view0.png');pim.save(S/'prepared0.png');(S/'prepared0.bin').write_bytes(data);prompt=prompts(task)[0]['text'];msg=[dict(role='system',content='You are a helpful assistant.'),dict(role='user',content=[dict(type='image',image=pim),dict(type='text',text=prompt)])];v=proc(text=[proc.apply_chat_template(msg,tokenize=False,add_generation_prompt=True)],images=[pim],return_tensors='pt');processor=dict(prompt_tokens=int(v['input_ids'].shape[-1]),grid=v['image_grid_thw'].tolist(),tensor_sha256=hashlib.sha256(v['pixel_values'].numpy().tobytes()).hexdigest());assert processor['prompt_tokens']+4096<=8192
  q=dict(ordinal=0,source=row['source'],raw=row['raw'],source_sha256=src,raw_sha256=sha(row['raw']),owner=owner,source_bbox=box,gate=c,prepared_size=list(pim.size),prepared_sha256=sha(S/'prepared0.bin'),pixel_sha256=pix(pim),identity=identity,prompt=prompt,parameters=params(task),processor=processor,mapping=dict(rect=rect,affine=[crop.width/pim.width,0,rect[0],0,crop.height/pim.height,rect[1]]))
  save(S/'prepared.json',[q]);save(S/'runtime_inputs.json',dict(inputs=str(base)));save(S/'budget.json',dict(maximum=1,reserved=0,sources={},owners={},identities=[]));save(S/'task.json',dict(task=task));save(S/'time_binding.json',json.loads((O/'admission.json').read_text()))
  from dependency_lock_0111_v1 import create
  create(S/'dependencies.json',['code/experimenter/prose_transport_0143_v1.py']);res=subprocess.run([sys.executable,'-B',str(R/'code/experimenter/prose_transport_0143_v1.py'),str(S),a.gpu,'--hidden']);answers=json.loads((S/'responses.json').read_text()) if (S/'responses.json').exists() else []
  if res.returncode or not answers or answers[0].get('finish')!='stop':return None,dict(reason='observation_failure',stage=str(S),returncode=res.returncode)
  return answers[0],dict(stage=str(S),prepared=q)
 for rank,row in enumerate(plan):
  if a.max_plan_rows and rank>=a.max_plan_rows:outcomes.append(dict(source=row['source'],decision='plan_window_native_fallback'));continue
  if row['decision']!='ready':outcomes.append(row);continue
  answer,meta=call(row,row['source_bbox'],'[layout]','risk_context');rec=dict(source=row['source'],layout=meta,text=[]);outcomes.append(rec)
  if answer is None:continue
  im=Image.open(row['source']);raw=json.loads(Path(row['raw']).read_bytes())
  try:blocks=parse(answer['text'],meta['prepared']['mapping']['rect'],im.size);ps=proposals(blocks,raw['blocks'],[b for g in row['groups'] for b in g],im.size)
  except (AssertionError,ValueError) as e:rec['fallback']='layout_parse';continue
  md_current=(base/'markdown'/(Path(row['raw']).stem+'.md')).read_bytes().decode()
  ps=[resolve(p,raw['blocks'],im,md_current) for p in ps]
  rec['proposals']=ps
  for j,p in enumerate(ps):
   owner='text_group:'+hashlib.sha256(json.dumps(p['source_bbox']).encode()).hexdigest();ans,mm=call(row,p['source_bbox'],'text',owner);rr=dict(proposal=p,observation=mm);rec['text'].append(rr)
   if ans is not None:changes.setdefault(row['raw'],[]).append((p,ans,rr))
  save(O/'outcomes.json',outcomes)
 for variant in ['generator','selected']:
  dest=O/(variant+'_predictions')
  for sub in ['raw','markdown']:
   (dest/sub).mkdir(parents=True,exist_ok=True)
   for f in (base/sub).iterdir():
    if f.is_file():os.link(f.resolve(),dest/sub/f.name)
  for path,items in changes.items():
   p=Path(path);rb=p.read_bytes().decode();md=(base/'markdown'/(p.stem+'.md')).read_bytes().decode()
   for q,ans,rec in sorted(items,key=lambda x:(x[0]['replace_owners'] or [x[0]['insert_before']])[0],reverse=True):
    try:rb,md,receipt=edit(rb,md,q,ans,variant=='selected');rec[variant]=dict(accepted=True,receipt=receipt)
    except (AssertionError,ValueError,KeyError,IndexError) as e:rec[variant]=dict(accepted=False,reason=str(e))
   for sub,ext,data in [('raw','.json',rb),('markdown','.md',md)]:
    f=dest/sub/(p.stem+ext);tmp=f.with_suffix('.tmp');tmp.write_bytes(data.encode());tmp.replace(f)
 save(O/'outcomes.json',outcomes);save(O/'completion.json',dict(status='COMPLETE',new_HTTP=json.loads(ledger.read_text())['reserved']-initial,prepare_seconds=prepare_seconds,wall_seconds=time.monotonic()-t,budget=str(ledger),capped=True))
if __name__=='__main__':main()
