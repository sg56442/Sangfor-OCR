"""Run completed core B then frozen common tail; --tail-existing never runs producers."""
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path
R=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--core',required=True);p.add_argument('--native',required=True);p.add_argument('--pages',required=True);p.add_argument('--out',required=True);p.add_argument('--receipt',required=True);p.add_argument('--core-spec');p.add_argument('--tail-existing',action='store_true');p.add_argument('--compare');a=p.parse_args()
 core,native,pages,out,receipt=[Path(x).resolve() for x in [a.core,a.native,a.pages,a.out,a.receipt]]
 assert out.is_relative_to(R/'code/experimenter') and receipt.is_relative_to(R/'code/experimenter')
 assert not out.exists() and not receipt.exists();receipt.parent.mkdir(parents=True,exist_ok=True)
 assert a.tail_existing != bool(a.core_spec)
 if a.core_spec:
  spec=json.loads(Path(a.core_spec).read_text());cmd=spec['argv'];assert Path(cmd[2]).resolve()==R/'code/experimenter/phase2_b_prime_v4.py'
  for flag,val in [('--out',str(core)),('--native-run',str(native)),('--pages',str(pages))]:assert cmd[cmd.index(flag)+1]==val
  subprocess.run(cmd,check=True,cwd=R)
 pipeline=core/'pipeline.json';state=json.loads(pipeline.read_text());assert state['status']=='COMPLETE' and state['inference_complete'] and state['native_run']==str(native)
 before=sha(pipeline)
 entry=R/'code/research/run_native_rules_track_a_v1.py';freeze=R/'reports/researcher_0006p/rules_freeze_v4.json'
 cmd=['unshare','--net',sys.executable,'-B',str(entry),'--native',str(native),'--pages',str(pages),'--out',str(out),'--freeze',str(freeze),'--profile','tail','--combined-tail',str(core/'combined')]
 start=time.monotonic();run=subprocess.run(cmd,cwd=R,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'));wall=time.monotonic()-start
 result=dict(status='COMPLETE' if run.returncode==0 else 'FAILED',returncode=run.returncode,mode='existing_core_actual_tail_execution' if a.tail_existing else 'fresh_core_then_tail',argv=cmd,wall_seconds=wall,network_namespace=True,GPU_visible=False,tail_model_requests=0,scored=False,core_pipeline_sha256=before,source_hashes={str(x):sha(x) for x in [Path(__file__),entry,freeze]},comparison=None)
 assert sha(pipeline)==before
 if run.returncode==0 and a.compare:
  ref=Path(a.compare);mismatches=[];n=0
  for sub,ext in [('raw','json'),('markdown','md')]:
   files=list((out/'predictions'/sub).glob('*.'+ext));assert len(files)==1651
   for f in files:
    n+=1
    if f.read_bytes()!=(ref/'predictions'/sub/f.name).read_bytes():mismatches.append(str(f.relative_to(out)))
  result['comparison']=dict(files=n,mismatches=mismatches,byte_equal=not mismatches)
  if mismatches:result.update(status='FAILED_PARITY',returncode=1)
 receipt.write_text(json.dumps(result,indent=2));raise SystemExit(result['returncode'])
if __name__=='__main__':main()
