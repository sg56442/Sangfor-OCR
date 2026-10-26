import json,sys,hashlib,time,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/research'),str(R/'code/experimenter')]
from single_model_selective_v1 import hidden
if '--isolated' not in sys.argv:subprocess.run(hidden(['unshare','--net',sys.executable,__file__,'--isolated']),check=True);raise SystemExit
from column_view_0059 import measure
from PIL import Image
import os
O=Path(os.environ['SPACING_OUT']);cfg=json.load(open(O/'inputs.json'));src=Path(cfg['inputs']);pages=json.load(open(cfg['manifest']));rows=[];start=time.monotonic();binding={}
for p in pages:
 rp=src/'raw'/(p['id']+'.json');rb=rp.read_bytes();binding[str(rp)]=hashlib.sha256(rb).hexdigest();raw=json.loads(rb);im=None
 for i,b in enumerate(raw['blocks']):
  if b['type']!='table':continue
  bb=b['bbox'];ww=bb[2]-bb[0];hh=bb[3]-bb[1]
  if ww<=0 or hh<=0 or hh<.3 or ww>.12:continue
  if im is None:im=Image.open(p['image']).convert('RGB')
  m=measure(im,b)
  if m is None:continue
  priority=hashlib.sha256(json.dumps(dict(content=b.get('content'),bbox=bb),sort_keys=True,ensure_ascii=False).encode()).hexdigest();rows.append(dict(source=p['image'],source_sha256=hashlib.sha256(Path(p['image']).read_bytes()).hexdigest(),raw=str(rp),raw_sha256=binding[str(rp)],owner=i,priority=priority,geometry=m))
rows.sort(key=lambda r:r['priority']);result=dict(pages=len(pages),prefilter=len(rows),risk=sum(x['geometry']['risk'] for x in rows),rows=rows,seconds=time.monotonic()-start);(O/'census.json').write_text(json.dumps(result,indent=2));(O/'input_binding.json').write_text(json.dumps(binding,indent=2));print({k:v for k,v in result.items() if k!='rows'})
