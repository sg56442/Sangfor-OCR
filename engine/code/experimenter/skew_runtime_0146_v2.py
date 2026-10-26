"""Fresh current-input skew-context pipeline; research/final permit separated."""
import argparse,sys,json,os,subprocess,time,hashlib,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/experimenter'),str(R/'code/runtime')]
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2))
def main():
 ap=argparse.ArgumentParser()
 for k in ['inputs','pages','out','ledger','dependency-lock','gpu']:ap.add_argument('--'+k,required=True)
 ap.add_argument('--budget',type=int,default=4);ap.add_argument('--final-validation-admission');ap.add_argument('--final-validation-sha256');ap.add_argument('--hidden',action='store_true');ap.add_argument('--prepare-only',action='store_true');a=ap.parse_args();O=Path(a.out).resolve();B=Path(a.inputs).resolve();pages=Path(a.pages).resolve();ledger=Path(a.ledger).resolve();dep=Path(a.dependency_lock).resolve()
 from skew_timegate_0146_v2 import check,input_hash,sha,source_hashes
 if not a.hidden:
  t=time.monotonic();assert ledger.exists();assert 0<=a.budget<=4;assert O.parent==R/'runs'
  if not a.final_validation_admission:assert 'sealed' not in str(B)
  else:
   # Validate final timing/freeze/dependencies before any sealed input bytes.
   permit=json.loads(Path(a.final_validation_admission).read_text());pre=dict(binding=permit['run_binding'],permit=a.final_validation_admission,permit_sha256=a.final_validation_sha256,dependency_lock=str(dep),ledger=str(ledger));check(R,pre,verify_input=False)
  leases=json.loads((R/'control/gpu_leases.json').read_text());lease=leases[a.gpu];state=json.loads(ledger.read_text())
  binding=dict(kind='skew_current_input',inputs=str(B),pages=str(pages),out=str(O),gpu=a.gpu,budget=a.budget,ledger=str(ledger),ledger_id=state['ledger_id'],source_cap=4,owner_cap=1,retry=0,input_sha256=input_hash(B,pages),dependency_lock_sha256=sha(dep),service=dict(endpoint=lease['endpoint'],container_id=lease['container_id']))
  cfg=dict(binding=binding,entry=str(Path(__file__).resolve()),permit=a.final_validation_admission,permit_sha256=a.final_validation_sha256,dependency_lock=str(dep),ledger=str(ledger));check(R,cfg)
  if O.exists():
   prior=json.loads((O/'time_binding.json').read_text());assert prior==cfg
   done=json.loads((O/'completion.json').read_text());assert done['status'] in ['COMPLETE','PREPARED'];print(json.dumps(dict(idempotent=True,HTTP=0,completion=done)));return
  O.mkdir();save(O/'runtime_inputs.json',dict(inputs=str(B)));save(O/'time_binding.json',cfg);shutil.copyfile(dep,O/'dependencies.json');(O/'budget.json').symlink_to(ledger);save(O/'admission_timing.json',dict(seconds=time.monotonic()-t));
  from panel_hidden_0110_v2 import restricted
  cmd=restricted(O,[sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--hidden']);os.execvp(cmd[0],cmd)
 cfg=json.loads((O/'time_binding.json').read_text());check(R,cfg);t=time.monotonic();initial=json.loads(ledger.read_text())['reserved']
 def run(name,*args):subprocess.run([sys.executable,'-B',str(R/'code/experimenter'/name),*map(str,args)],check=True)
 run('skew_census_0146_v3.py','--inputs',B,'--out',O,'--pages',pages);run('skew_prepare_0146_v3.py',O);prepare=time.monotonic()-t
 if not a.prepare_only:
  if json.loads((O/'prepared.json').read_text()):run('skew_transport_0146_v2.py',O,a.gpu,'--hidden')
  else:save(O/'responses.json',[]);save(O/'execution.json',dict(actual_HTTP=0,status='COMPLETE_NO_REQUEST',GT_hidden=True))
  run('skew_compose_0146_v2.py',O)
 save(O/'completion.json',dict(status='PREPARED' if a.prepare_only else 'COMPLETE',new_HTTP=json.loads(ledger.read_text())['reserved']-initial,prepare_seconds=prepare,wall_seconds=time.monotonic()-t,admission_seconds=json.loads((O/'admission_timing.json').read_text())['seconds'],GT_history_hidden=True))
if __name__=='__main__':main()
