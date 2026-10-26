"""Offline same-run response validation CLI; never import historical winners."""
import argparse,json,os,hashlib
from pathlib import Path
from PIL import Image
from spacing_geometry_0042 import bind
from spacing_gate_0042 import grid
ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--manifest',required=True);ap.add_argument('--bundle',required=True);ap.add_argument('--out',required=True);ap.add_argument('--arm',choices=['generator','selector'],required=True);a=ap.parse_args();src=Path(a.inputs);out=Path(a.out);out.mkdir(parents=True,exist_ok=False);pages=json.load(open(a.manifest));bundle=json.load(open(a.bundle));records=[]
for sub in ['raw','markdown']:
 (out/sub).mkdir()
 for p in (src/sub).iterdir():
  if p.is_file():os.link(p,out/sub/p.name)
for r in bundle:
 p=pages[r['manifest_index']];rp=src/'raw'/(p['id']+'.json');raw=json.load(rp.open());old=raw['blocks'][r['owner']]['content'];new=r['html'];decision=dict(accepted=False,reason='input_owner_changed')
 if old==new:decision=dict(accepted=True,reason='identity')
 elif hashlib.sha256(old.encode()).hexdigest()==r['before_sha256']:
  assert hashlib.sha256(Path(p['image']).read_bytes()).hexdigest()==r['source_sha256'];b=raw['blocks'][r['owner']];im=Image.open(p['image']).convert('RGB');w,h=im.size;im=im.crop(tuple(v*s for v,s in zip(b['bbox'],[w,h,w,h]))).rotate(b.get('angle',0),expand=True)
  decision=bind(im,old,new)
 valid=grid(new) is not None;apply=valid and (a.arm=='generator' or decision['accepted']) and old!=new
 if apply:
  mdp=src/'markdown'/(p['id']+'.md');md=mdp.read_text();assert md.count(old)==1;raw['blocks'][r['owner']]['content']=new
  for sub,ext,s in [('raw','json',json.dumps(raw,ensure_ascii=False,indent=2)),('markdown','md',md.replace(old,new,1))]:
   target=out/sub/(p['id']+'.'+ext);target.unlink();target.write_text(s)
 records.append(dict(manifest_index=r['manifest_index'],owner=r['owner'],decision=decision,applied=apply,valid_grid=valid))
(out/'receipt.json').write_text(json.dumps(dict(arm=a.arm,records=records,changed=sum(r['applied'] for r in records),files=sum(1 for sub in ['raw','markdown'] for p in (out/sub).iterdir()),HTTP=0),indent=2));print([(r['manifest_index'],r['decision']['reason'],r['applied']) for r in records])
