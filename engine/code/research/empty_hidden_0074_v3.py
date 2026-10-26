"""Hide GT plus all prior run/report directories except current input/output and admission files."""
import json
from pathlib import Path
from single_model_selective_v1 import hidden
R=Path(__file__).resolve().parents[2]
def restricted(out,argv):
 out=Path(out).resolve();cfg=json.load(open(out/'time_binding.json'));allowed=Path(cfg['binding']['inputs']).resolve();files=[Path(cfg[k]).resolve() for k in ['dependency_lock','ledger','permit'] if cfg.get(k)];keep=[out,allowed]
 paths=[]
 for parent in [R/'code/experimenter/runs',R/'code/research/runs',R/'code/runtime/runs',R/'runs',R/'reports']:
  if not parent.exists():continue
  for p in parent.iterdir():
   if not p.is_dir():continue
   if any(k.is_relative_to(p.resolve()) for k in keep):continue
   if any(k.is_relative_to(p.resolve()) for k in files):
    paths.extend(z for z in p.iterdir() if z.is_dir() and not any(k.is_relative_to(z.resolve()) for k in keep+files))
   else:paths.append(p)
 script='set -euo pipefail\nn="$1"; shift\nfor ((i=0;i<n;i++)); do mount -t tmpfs -o size=4k,mode=000 none "$1"; shift; done\nexec "$@"'
 return hidden(['/bin/bash','-c',script,'no-old-response',str(len(paths)),*map(str,paths),*argv])
