import argparse,os,sys,json,time,subprocess,ast,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/research'),str(R/'code/experimenter')]
from single_model_selective_v1 import hidden,MODEL
from spacing_state_0044 import save,sha
p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','observe','compose','permit']);p.add_argument('--inputs');p.add_argument('--pages');p.add_argument('--out',required=True);p.add_argument('--gpu',default='3');p.add_argument('--budget',type=int,default=8);p.add_argument('--native-inputs');p.add_argument('--native-audit');p.add_argument('--lane-plan');p.add_argument('--final-permit');p.add_argument('--final-permit-sha');p.add_argument('--isolated',action='store_true');a=p.parse_args()
if not a.isolated:
 cmd=[sys.executable,__file__,*sys.argv[1:],'--isolated'];cmd=cmd if a.mode=='observe' else ['unshare','--net',*cmd];subprocess.run(hidden(cmd),check=True);raise SystemExit
O=Path(a.out).resolve();O.mkdir(parents=True,exist_ok=True);os.environ['SPACING_OUT']=str(O)
if a.final_permit:os.environ['SPACING_PERMIT']=str(Path(a.final_permit).resolve());os.environ['SPACING_PERMIT_SHA']=a.final_permit_sha
if a.mode=='prepare':
 assert 0<=a.budget<=8 and a.inputs and a.pages and a.native_inputs and a.native_audit
 cfg=dict(inputs=str(Path(a.inputs).resolve()),manifest=str(Path(a.pages).resolve()),native_inputs=str(Path(a.native_inputs).resolve()),native_audit=str(Path(a.native_audit).resolve()),model=str(MODEL),gpu=a.gpu,budget=a.budget)
 if a.lane_plan:cfg['lane_plan']=str(Path(a.lane_plan).resolve())
 save(O/'inputs.json',cfg);dirs=[R/'code/research',R/'code/experimenter',R/'code/runtime',R/'scripts'];todo=[Path(__file__),R/'code/research/column_prepare_0063.py',R/'code/research/column_census_0060.py',R/'code/research/column_compose_0063.py',R/'code/research/column_observe_0063.py',R/'code/research/spacing_processor_0043.py',R/'code/research/spacing_admit_0044.py'];seen={}
 while todo:
  f=todo.pop().resolve()
  if str(f) in seen:continue
  seen[str(f)]=sha(f)
  for n in ast.walk(ast.parse(f.read_text())):
   names=([n.module] if isinstance(n,ast.ImportFrom) and n.module else [x.name for x in n.names] if isinstance(n,ast.Import) else [])
   for name in names:
    for dr in dirs:
     q=dr/(name.replace('.','/')+'.py')
     if q.exists():todo.append(q);break
 save(O/'code_lock.json',seen);start=time.monotonic();subprocess.run([sys.executable,str(R/'code/research/column_prepare_0063.py')],check=True);save(O/'prepare_timing.json',dict(seconds=time.monotonic()-start,HTTP=0))
elif a.mode=='permit':
 from column_admission_0063 import request
 save(O/'permit_request.json',request(O))
else:subprocess.run([sys.executable,str(R/'code/research'/('column_observe_0063.py' if a.mode=='observe' else 'column_compose_0063.py'))],check=True)
