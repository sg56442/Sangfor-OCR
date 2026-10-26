"""Freeze local transitive AST imports plus native client, imported binaries and distribution manifests."""
import ast,sys,json,hashlib,importlib,importlib.metadata,datetime
from pathlib import Path
R=Path(__file__).resolve().parents[2];SEARCH=[R/'code/experimenter',R/'code/runtime',R/'code/research',R/'scripts']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(path):
 d=json.loads(Path(path).read_text())
 for p,h in d['files'].items():assert sha(p)==h,'Dependency changed: '+p
 return d

def create(path,entries):
 paths=set();pending=[R/p for p in entries]
 while pending:
  p=pending.pop().resolve()
  if p in paths:continue
  paths.add(p)
  if p.suffix!='.py':continue
  tree=ast.parse(p.read_text())
  for n in ast.walk(tree):
   names=[a.name for a in n.names] if isinstance(n,ast.Import) else [n.module] if isinstance(n,ast.ImportFrom) and n.module else []
   for name in names:
    for parent in SEARCH:
     q=parent/(name.replace('.','/')+'.py')
     if q.exists():pending.append(q)
 for parent in SEARCH:sys.path.insert(0,str(parent))
 # Import-only native transport preflight. No client created, no HTTP.
 import os
 os.environ['FT1021_AUDIT_DIR']=str(Path(path).parent/'import_only_audit')
 for module in ['mineru_vl_utils','http_audit','native_wire_audit_v1','http_budget_v1','panel_group_gate_0109_v1','cv2','numpy','PIL.Image','transformers']:
  importlib.import_module(module)
 import mineru_vl_utils
 paths.update(Path(mineru_vl_utils.__file__).parent.rglob('*.py'))
 for module in list(sys.modules.values()):
  f=getattr(module,'__file__',None)
  if f and Path(f).is_file() and not str(f).endswith('.pyc'):paths.add(Path(f).resolve())
 # Installed distributions pin the remainder of lazy package trees through RECORD manifests.
 distributions={}
 for d in importlib.metadata.distributions():
  name=d.metadata.get('Name','unknown');distributions[name]=d.version
  for f in d.files or []:
   if str(f).endswith('.dist-info/RECORD'):
    q=Path(d.locate_file(f));
    if q.exists():paths.add(q.resolve())
 paths.add(Path(sys.executable).resolve())
 data={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':{str(p):sha(p) for p in sorted(paths)},'distributions':distributions,'entries':entries,'scope':'Local AST closure including explicit dynamic worker/processor entrypoints; full MinerU client Python tree; imported module files/binaries; installed distribution RECORD manifests. No model weight copying.'}
 Path(path).write_text(json.dumps(data,indent=2)+'\n');verify(path);return data
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--lock',required=True);ap.add_argument('--create',action='store_true');a=ap.parse_args()
 if a.create:create(a.lock,['code/experimenter/execute_panel_0111_v1.py','code/experimenter/observe_panels_0111_v1.py','scripts/processor_replay_stream_v1.py','scripts/launch_owned.py','code/experimenter/panel_current_0110_v1.py','code/experimenter/panel_hidden_0110_v2.py'])
 else:verify(a.lock)
