"""Portable full input census; source identities used only for bindings/order/budget."""
import json,sys,time,hashlib,argparse,math
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'code/experimenter'))
from skew_group_0146_v1 import risk
a=argparse.ArgumentParser();a.add_argument('--inputs',required=True);a.add_argument('--out',required=True);a.add_argument('--pages',required=True);a=a.parse_args();O=Path(a.out).resolve();B=Path(a.inputs).resolve();O.mkdir(exist_ok=True,parents=True);t=time.monotonic();rows=[];counts={};bindings={}
for p in sorted((B/'raw').glob('*.json')):
 src=next(Path(a.pages)/(p.stem+e) for e in ['.png','.jpg'] if (Path(a.pages)/(p.stem+e)).exists());md=B/'markdown'/f'{p.stem}.md';bs=json.loads(p.read_bytes())['blocks'];im=Image.open(src)
 for f in [p,md,src]:bindings[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
 valid=all(isinstance(b,dict) and isinstance(b.get('bbox'),list) and len(b['bbox'])==4 and all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in b['bbox']) and b['bbox'][2]>b['bbox'][0] and b['bbox'][3]>b['bbox'][1] for b in bs)
 d=risk(im,bs) if valid else dict(accepted=False,reason='invalid_geometry')
 counts[d['reason']]=counts.get(d['reason'],0)+1
 if d['reason'] in ['overlap_with_source_skew','source_skew_not_supported']:rows.append(dict(source=str(src),raw=str(p),source_sha256=bindings[str(src)],gate=d))
from single_model_selective_v1 import HIDDEN
hidden=all(Path(p).stat().st_size==0 for p in HIDDEN)
(O/'census.json').write_text(json.dumps(dict(pages=len(list((B/'raw').glob('*.json'))),counts=counts,rows=rows,bindings=bindings,seconds=time.monotonic()-t,GT_hidden=hidden),ensure_ascii=False,indent=2));print(counts,'sec',time.monotonic()-t,'hidden',hidden)
