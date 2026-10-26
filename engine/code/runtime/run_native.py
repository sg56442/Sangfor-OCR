"""Run an owned native job with GT hidden in a private mount namespace."""
import argparse,json,os,pathlib,subprocess,time,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--pages',required=True);p.add_argument('--out',required=True);p.add_argument('--port',type=int,default=28521);p.add_argument('--audit',action='store_true');a=p.parse_args()
out=pathlib.Path(a.out).resolve();assert out.is_relative_to(ROOT);out.mkdir(exist_ok=True,parents=True)
assert not (out/'predictions').exists()
meta=json.load(open(ROOT/'agents/shared/runtime.json'))
for attempt in range(240):
 try:
  with urllib.request.urlopen(f'http://127.0.0.1:{a.port}/v1/models',timeout=2) as r:assert r.status==200
  break
 except Exception:time.sleep(5)
else:raise RuntimeError('Server readiness timeout')
model=meta['model'];hidden=['/opt/p2t10/hidden/OmniDocBench.json','/opt/p2t10/hidden/source_validation_v2_references.jsonl','/opt/p2t10/hidden/source_validation_v1_references.jsonl']
script='set -euo pipefail\nn="$1"; shift\nfor ((i=0;i<n;i++)); do mount --bind /dev/null "$1"; test ! -s "$1"; shift; done\nexec "$@"'
cmd=['unshare','--mount','--propagation','private','/bin/bash','-c',script,'ft1021-no-gt',str(len(hidden)),*hidden,meta['python'],'-B',str(ROOT/'code/runtime'/('audited_worker.py' if a.audit else 'native_worker.py')),'--pages',str(pathlib.Path(a.pages).resolve()),'--expected-count',str(len(json.load(open(a.pages)))),'--model',model,'--weight-sha256','01dcb5addfa1d6133fd0930e79fa2484817cb0228af21cb4917fa73d04fa3147','--port',str(a.port),'--output',str(out/'predictions')]
env=dict(os.environ,FT1021_AUDIT_DIR=str(out/'audit'),PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='')
start=time.time()
with (out/'worker.log').open('w') as f:
 proc=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,env=env)
 (out/'ownership.json').write_text(json.dumps(dict(pid=proc.pid,start_ticks=pathlib.Path(f'/proc/{proc.pid}/stat').read_text().split()[21],command=cmd,started=start),indent=2));rc=proc.wait()
(out/'run.json').write_text(json.dumps(dict(returncode=rc,elapsed_seconds=time.time()-start,audited=a.audit),indent=2))
raise SystemExit(rc)
