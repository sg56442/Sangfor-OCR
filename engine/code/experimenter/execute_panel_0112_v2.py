"""Single fresh fixed candidate execution; inputs manifest, native predictions, admitted output.
Requires frozen source/dependency hashes and preflight in output before starting.
No score/GT stage in this executor. Run under launch_owned for long manifests.
"""
import argparse,json,subprocess,sys,concurrent.futures,time
from pathlib import Path
R=Path(__file__).resolve().parents[2]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',required=True);ap.add_argument('--inputs',required=True);ap.add_argument('--out',required=True);ap.add_argument('--gpus',default='0,1');ap.add_argument('--final-permit');ap.add_argument('--final-permit-sha256');a=ap.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
 from initialize_panel_0112_v2 import initialize
 initialize(a.manifest,a.inputs,out,[int(x) for x in a.gpus.split(',')])
 timings={};pipeline_start=time.monotonic()
 from dependency_lock_0111_v1 import verify
 verify(out/'dependencies.json')
 from panel_admission_0112_v2 import run_binding,admitted_deadline,sha
 gpus=[int(x) for x in a.gpus.split(',')];assert gpus and len(set(gpus))==len(gpus) and set(gpus)<={0,1,3}
 binding=run_binding(a.manifest,a.inputs,out,gpus);bp=out/'admission_binding.json'
 if bp.exists():assert json.loads(bp.read_text())==binding,'Input/manifest/out/budget binding changed'
 else:bp.write_text(json.dumps(binding,indent=2))
 if a.final_permit:
  assert a.final_permit_sha256 and sha(a.final_permit)==a.final_permit_sha256
  local_permit=out/'final_permit.json';payload=Path(a.final_permit).read_bytes()
  if local_permit.exists():assert local_permit.read_bytes()==payload
  else:local_permit.write_bytes(payload)
  a.final_permit=str(local_permit)
 admitted_deadline(R,out,a.final_permit,a.final_permit_sha256)
 cfg={'inputs':str(Path(a.inputs).resolve()),'manifest':str(Path(a.manifest).resolve())};p=out/'executor_inputs.json'
 if p.exists():assert json.loads(p.read_text())==cfg,'Cannot resume against changed inputs'
 else:p.write_text(json.dumps(cfg))
 assert (out/'freeze_transport_v2.json').exists() and json.loads((out/'preflight.json').read_text())['status']=='PASS'
 (out/'runtime_inputs.json').write_text(json.dumps(cfg))
 manifest_bytes=Path(a.manifest).read_bytes();local_manifest=out/'input_manifest.json'
 if local_manifest.exists():assert local_manifest.read_bytes()==manifest_bytes,'Manifest changed'
 else:local_manifest.write_bytes(manifest_bytes)
 a.manifest=str(local_manifest)
 def stage(name):
  t=time.monotonic();subprocess.run([sys.executable,'-B',str(R/'code/experimenter/panel_hidden_0110_v2.py'),str(out),sys.executable,'-B',str(R/'code/experimenter/panel_current_0110_v1.py'),'--manifest',a.manifest,'--inputs',a.inputs,'--out',str(out),'--stage',name],check=True)
  timings[name]=time.monotonic()-t
 if not (out/'census.json').exists():stage('scan')
 from dependency_lock_0111_v1 import sha
 for rp,rh,sp,sh,mp,mh in json.loads((out/'census.json').read_text())['bindings']:
  assert sha(rp)==rh and sha(sp)==sh and sha(mp)==mh,'Resume input binding mismatch'
 # Any partial failed worker is retained, never blindly restarted or resampled.
 for phase in ['layout','recognition']:
  if phase=='recognition' and not (out/'plan_recognition.json').exists():stage('text')
  def worker(gpu):
   d=out/f'gpu{gpu}_attempt{phase}';state=d/'execution.json'
   if state.exists():assert json.loads(state.read_text())['status'] in ['COMPLETE','COMPLETE_WITH_FAILURES'];return
   subprocess.run([sys.executable,'-B',str(R/'code/experimenter/observe_panels_0112_v2.py'),'--out',str(out),'--gpu',str(gpu),'--lane-index',str(gpus.index(gpu)),'--lane-count',str(len(gpus)),'--attempt',phase,'--plan',f'plan_{phase}.json']+(['--final-permit',a.final_permit,'--final-permit-sha256',a.final_permit_sha256] if a.final_permit else []),check=True)
  t=time.monotonic()
  with concurrent.futures.ThreadPoolExecutor(max_workers=len(gpus)) as pool:list(pool.map(worker,gpus))
  timings[phase+'_workers_makespan']=time.monotonic()-t
 if not (out/'selection.json').exists():stage('compose')
 timings['pipeline_seconds']=time.monotonic()-pipeline_start
 tp=out/('resume_timings.json' if (out/'pipeline_timings.json').exists() else 'pipeline_timings.json');tp.write_text(json.dumps(timings,indent=2))
 print(json.dumps({'status':'COMPLETE','selection':str(out/'selection.json')}))
if __name__=='__main__':main()
