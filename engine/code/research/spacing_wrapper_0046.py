"""Public CLI. CPU stages offline; inference GT-hidden. RSI alone approves permits."""
import os,sys,subprocess,json,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'code/experimenter'))
from single_model_selective_v1 import hidden
ENTRY=R/'code/research/spacing_runtime_0046.py'
def command(args):
 stage=args[0];out=Path(args[args.index('--out')+1]).resolve()
 allowed=[out]
 if (out/'inputs.json').exists():
  c=json.loads((out/'inputs.json').read_text());allowed += [Path(c[k]).resolve() for k in ['inputs','native_inputs','native_audit','manifest']]
 else:
  for flag in ['--inputs','--native-inputs','--native-audit','--manifest']:
   if flag in args:allowed.append(Path(args[args.index(flag)+1]).resolve())
 paths=[]
 for parent in [R/'runs',R/'code/research/runs',R/'code/experimenter/runs',R/'code/runtime/runs',R/'reports',R/'evidence']:
  if parent.exists():
   paths.extend(p for p in parent.iterdir() if p.is_dir() and not any(a==p.resolve() or a.is_relative_to(p.resolve()) for a in allowed))
 script='set -euo pipefail\nn="$1"; shift\nfor ((i=0;i<n;i++)); do mount -t tmpfs -o size=4k,mode=000 none "$1"; shift; done\nexec "$@"'
 inner=[sys.executable,str(ENTRY),*args]
 if stage!='infer':inner=['unshare','--net',*inner]
 return hidden(['/bin/bash','-c',script,'spacing-isolated',str(len(paths)),*map(str,paths),*inner])
def main():
 args=sys.argv[1:]
 if not args or args[0] in ['--help','-h']:
  subprocess.run([sys.executable,str(ENTRY),'--help'],check=True);return
 if args[0]=='run':
  subprocess.run(command(['infer',*args[1:]]),check=True)
  subprocess.run(command(['apply',*args[1:]]),check=True)
 else:subprocess.run(command(args),check=True)
if __name__=='__main__':main()
