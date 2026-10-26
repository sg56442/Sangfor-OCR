from pathlib import Path
import json
from single_model_selective_v1 import hidden
R=Path(__file__).resolve().parents[2]
def restricted(out,argv):
 out=Path(out).resolve();cfg=json.loads((out/'runtime_inputs.json').read_text());allowed=Path(cfg['inputs']).resolve()
 paths=[]
 for parent in [R/'code/experimenter/runs',R/'code/research/runs',R/'code/runtime/runs',R/'runs']:
  if parent.exists():
   paths += [p for p in parent.iterdir() if p.is_dir() and p.resolve()!=out and not allowed.is_relative_to(p.resolve())]
 script='set -euo pipefail\nn="$1"; shift\nfor ((i=0;i<n;i++)); do mount -t tmpfs -o size=4k,mode=000 none "$1"; shift; done\nexec "$@"'
 return hidden(['/bin/bash','-c',script,'no-old-response',str(len(paths)),*map(str,paths),*argv])
if __name__=='__main__':
 import sys,os
 c=restricted(sys.argv[1],sys.argv[2:]);os.execvp(c[0],c)
