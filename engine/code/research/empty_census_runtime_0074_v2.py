import argparse,json,sys,time,hashlib
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/research'),str(R/'code/experimenter')]
from empty_cell_0074_v2 import candidates
p=argparse.ArgumentParser();p.add_argument('--inputs');p.add_argument('--pages');p.add_argument('--out');a=p.parse_args();O=Path(a.out);t=time.monotonic();rows=[];bindings={};images={p.stem:p for p in Path(a.pages).iterdir() if p.is_file()}
for rp in sorted((Path(a.inputs)/'raw').glob('*.json')):
 src=images[rp.stem];mp=Path(a.inputs)/'markdown'/(rp.stem+'.md')
 for f in [src,rp,mp]:bindings[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
 for i,b in enumerate(json.loads(rp.read_bytes())['blocks']):
  if b['type']!='table' or '<td></td>' not in b.get('content',''):continue
  with Image.open(src) as im:cs=candidates(im,b)
  for c in cs:
   j=len(rows);c.pop('crop').save(O/f'cell{j}.png');rows.append(dict(ordinal=j,source=str(src),raw=str(rp),owner=i,block=b,source_sha256=bindings[str(src)],raw_sha256=bindings[str(rp)],**c))
(O/'census.json').write_text(json.dumps(dict(pages=len(bindings)//3,rows=rows,bindings=bindings,seconds=time.monotonic()-t),ensure_ascii=False,indent=2))
