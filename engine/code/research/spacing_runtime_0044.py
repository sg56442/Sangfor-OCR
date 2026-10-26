"""Fixed numeric-baseline pipeline with durable no-retry accounting; selector output only."""
import argparse,json,os,sys,subprocess,hashlib,ast
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'code/research'))
from spacing_state_0044 import *
ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','infer','apply']);ap.add_argument('--out',required=True);ap.add_argument('--inputs');ap.add_argument('--manifest');ap.add_argument('--native-audit');ap.add_argument('--native-inputs');ap.add_argument('--model');ap.add_argument('--budget',type=int,default=16);ap.add_argument('--gpu',choices=['3','1'],default='3');a=ap.parse_args();O=Path(a.out).resolve();os.environ['SPACING_OUT']=str(O)
def run(script,*args):subprocess.run([sys.executable,str(R/'code/research'/script),*map(str,args)],check=True)
def validate():
 for p,h in load(O/'dependencies.json').items():assert sha(p)==h,('dependency',p)
 for p,h in load(O/'input_binding.json').items():assert sha(p)==h,('input',p)
if a.stage=='prepare':
 assert 0<=a.budget<=16;assert all([a.inputs,a.manifest,a.native_audit,a.native_inputs,a.model]);O.mkdir(parents=True,exist_ok=False)
 cfg={k:str(Path(getattr(a,k)).resolve()) for k in ['inputs','manifest','model','native_audit','native_inputs']};cfg.update(budget=a.budget,gpu=a.gpu);save(O/'inputs.json',cfg);os.environ['SPACING_NATIVE_AUDIT']=cfg['native_audit']
 save(O/'contract.json',dict(authorization='D0309',risk='Unchanged spacing_gate_0042.risk',selector='Unchanged spacing_geometry_0042.bind',view='Unchanged0043 full upright owner + reversible uniform source-whitespace rows',budget=a.budget,owner_limit=1,assembly='Entire completed response only; unknown/incomplete/failed/overbudget fallback native',oracle='待测',net_pp='待测',stop='Selected source damage or no selected benefit; no parameter tuning'))
 run('spacing_gate_0042.py','--inputs',cfg['inputs'],'--manifest',cfg['manifest'],'--out',O/'census.json');run('spacing_prepare_0043.py');run('spacing_processor_0043.py',cfg['model']);run('spacing_admit_0044.py')
 pages=load(cfg['manifest']);assert len({p['id'] for p in pages})==len(pages);binding={str(O/'inputs.json'):sha(O/'inputs.json'),cfg['manifest']:sha(cfg['manifest']),cfg['native_audit']:sha(cfg['native_audit'])}
 for p in pages:
  for sub,ext in [('raw','json'),('markdown','md')]:
   f=Path(cfg['inputs'])/sub/(p['id']+'.'+ext);binding[str(f)]=sha(f)
 upstream=[]
 for q in load(O/'processor_plan.json'):
  nr=Path(cfg['native_inputs'])/'raw'/Path(q['raw']).name;raw=load(q['raw']);b=raw['blocks'][q['owner']];native=load(nr);matches=[i for i,z in enumerate(native['blocks']) if z['type']=='table' and z['bbox']==b['bbox'] and z.get('angle',0)==b.get('angle',0)];assert len(matches)==1,('native owner binding ambiguous',q['index']);upstream.append(dict(index=q['index'],native_raw=str(nr),native_raw_sha256=sha(nr),native_owner=matches[0],current_owner=q['owner'],native_request=q['native_receipt']['request_sha256']));binding[str(nr)]=sha(nr);binding[q['source']]=q['source_sha256']
 for f in ['processor_plan.json','contract.json','dedup.json']:binding[str(O/f)]=sha(O/f)
 save(O/'input_binding.json',binding);save(O/'native_binding.json',upstream)
 # Hash transitive campaign code imports plus native library implementation/config.
 dirs=[R/'code/research',R/'code/experimenter',R/'code/runtime'];todo=[Path(__file__)]+[R/'code/research'/s for s in ['spacing_prepare_0043.py','spacing_processor_0043.py','spacing_admit_0044.py','spacing_observe_0044.py','spacing_apply_0042.py']];seen=set()
 while todo:
  f=todo.pop().resolve()
  if f in seen:continue
  seen.add(f)
  for node in ast.walk(ast.parse(f.read_text())):
   mods=[node.module] if isinstance(node,ast.ImportFrom) and node.module else [x.name for x in node.names] if isinstance(node,ast.Import) else []
   for mod in mods:
    for d in dirs:
     q=d/(mod.split('.')[0]+'.py')
     if q.exists() and q not in seen:todo.append(q)
 import mineru_vl_utils
 seen.update(Path(mineru_vl_utils.__file__).parent.rglob('*.py'))
 seen.update(p for p in Path(cfg['model']).iterdir() if p.suffix in ['.json','.jinja','.txt'])
 save(O/'dependencies.json',{str(f):sha(f) for f in sorted(seen)})
elif a.stage=='infer':validate();run('spacing_observe_0044.py')
else:
 validate();cfg=load(O/'inputs.json');state=load(O/'ledger.json');assert not state.get('protocol_fatal');from mineru_vl_utils.post_process import simple_process
 from mineru_vl_utils.structs import ContentBlock
 pages=load(cfg['manifest']);ix={p['id']:i for i,p in enumerate(pages)};bundle=[];out=O/'selector_predictions'
 for q in load(O/'processor_plan.json'):
  t=q['tasks'][0];key=hashlib.sha256(json.dumps(dict(pixel=t['pixel_sha256'],prompt=t['prompt'],parameters=t['parameters']),sort_keys=True).encode()).hexdigest();z=state['records'].get(key,{})
  if z.get('status')!='COMPLETE':continue
  assert z['response']['choices'][0]['finish_reason']=='stop';old=load(q['raw'])['blocks'][q['owner']]['content'];new=simple_process([ContentBlock(type='table',bbox=[0,0,1,1],content=z['text'])])[0].content
  save(O/f'candidate_{q["index"]}.json',dict(index=q['index'],before=old,after=new,request_sha256=z['request_sha256']))
  bundle.append(dict(manifest_index=ix[Path(q['raw']).stem],owner=q['owner'],source_sha256=q['source_sha256'],before_sha256=hashlib.sha256(old.encode()).hexdigest(),html=new))
 save(O/'bundle.json',bundle)
 # Re-applying a completed immutable same-run result does no writes or network.
 if out.exists():
  assert load(O/'applied_binding.json')==dict(bundle_sha256=sha(O/'bundle.json'),input_binding_sha256=sha(O/'input_binding.json'))
 else:
  run('spacing_apply_0042.py','--inputs',cfg['inputs'],'--manifest',cfg['manifest'],'--bundle',O/'bundle.json','--out',out,'--arm','selector');save(O/'applied_binding.json',dict(bundle_sha256=sha(O/'bundle.json'),input_binding_sha256=sha(O/'input_binding.json')))
 save(O/'cost.json',costs(state,O/'audit/http.jsonl'))
