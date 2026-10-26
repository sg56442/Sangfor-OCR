"""Fresh bounded brace runtime; explicit RSI final admission uses shared unchanged time gate."""
import argparse,subprocess,sys,json,os,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'code/experimenter'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--pages',required=True);p.add_argument('--out',required=True);p.add_argument('--gpu',choices=['0','1','3'],required=True);p.add_argument('--budget',type=int,default=8);p.add_argument('--final-validation-admission');p.add_argument('--final-validation-sha256');p.add_argument('--check-time-only',action='store_true');a=p.parse_args();assert 0<=a.budget<=8
 base=Path(a.inputs).resolve();O=Path(a.out).resolve();assert O.parent==R/'runs';imgs={p.stem:p for p in Path(a.pages).iterdir() if p.is_file()};files=sorted((base/'raw').glob('*.json'));assert len(files)==1651
 fingerprints=[(p.name,sha(p),sha(base/'markdown'/(p.stem+'.md')),sha(imgs[p.stem])) for p in files];binding=dict(kind='brace_current_input',input_tree_sha256=hashlib.sha256(json.dumps(fingerprints).encode()).hexdigest(),inputs=str(base),pages=str(Path(a.pages).resolve()),out=str(O),gpu=a.gpu,budget=a.budget)
 from phase2_final_time_gate_v1 import deadline
 end=deadline(R,__file__,binding,a.final_validation_admission,a.final_validation_sha256)
 if a.check_time_only:print(json.dumps(dict(status='TIME_ADMISSION_PASS',deadline=end.isoformat(),time_binding=binding,HTTP=0)));return
 if not O.exists():O.mkdir();(O/'runtime_inputs.json').write_text(json.dumps(dict(inputs=str(base))))
 admit=O/'runtime_admission.json'
 if admit.exists():assert json.loads(admit.read_text())['time_binding']==binding
 else:admit.write_text(json.dumps(dict(time_binding=binding),indent=2))
 prep=[sys.executable,'-B',str(R/'code/experimenter/brace_production_0136_v5.py'),'--inputs',str(base),'--pages',a.pages,'--out',str(O),'--gpu',a.gpu,'--budget',str(a.budget)];subprocess.run(prep,check=True)
 from dependency_lock_0111_v1 import verify
 verify(O/'dependencies.json')
 cmd=[sys.executable,'-B',str(R/'code/experimenter/brace_transport_0136_v3.py'),str(O),a.gpu]
 if a.final_validation_admission:cmd+=['--final-validation-admission',a.final_validation_admission,'--final-validation-sha256',a.final_validation_sha256]
 result=subprocess.run(cmd)
 if not (O/'responses.json').exists():(O/'responses.json').write_text('[]')
 from panel_hidden_0110_v2 import restricted
 subprocess.run(['unshare','--net',*restricted(O,[sys.executable,'-B',str(R/'code/experimenter/brace_compose_0136_v4.py'),str(O)])],check=True)
 (O/'runtime_completion.json').write_text(json.dumps(dict(observation_returncode=result.returncode,budget=a.budget,selected_output=str(O/'selected_predictions'),fallback_on_failed_or_missing_response=True)))
if __name__=='__main__':main()
