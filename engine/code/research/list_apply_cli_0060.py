import sys,json,os,subprocess,hashlib,collections,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'scripts'),str(R/'code/research'),str(R/'code/experimenter')]
from single_model_selective_v1 import hidden
if '--isolated' not in sys.argv:subprocess.run(hidden(['unshare','--net',sys.executable,__file__,*sys.argv[1:],'--isolated']),check=True);raise SystemExit
from list_columns_0060_v2 import candidate
from phase2_array_label_runtime_v1 import block_spans
from repeated_runtime_0048b import patch
from spacing_apply_0046 import span
from PIL import Image
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--pages',required=True);ap.add_argument('--out',required=True);ap.add_argument('--isolated',action='store_true');args=ap.parse_args();O=Path(args.out).resolve();O.mkdir(exist_ok=True);src=Path(args.inputs).resolve();pages=json.load(open(args.pages));records=[];counts=collections.Counter();start=time.monotonic()
for sub in ['raw','markdown']:(O/'generator_predictions'/sub).mkdir(parents=True,exist_ok=False)
for p in pages:
 rp=src/'raw'/(p['id']+'.json');rb=rp.read_bytes();raw=json.loads(rb);md=(src/'markdown'/(p['id']+'.md')).read_bytes();re=[];me=[];im=None
 for i,b in enumerate(raw['blocks']):
  if b['type']!='table':continue
  if im is None:im=Image.open(p['image'])
  c,reason=candidate(im,b);counts[reason]+=1
  if c is None:continue
  try:
   sp=block_spans(rb,raw);edit=span(md,b['content'],c['text']);nb=dict(b,type='text',content=c['text']);re.append((*sp[i],json.dumps(nb,ensure_ascii=False).encode()));me.append(edit)
  except (AssertionError,KeyError,ValueError):counts['ambiguous_bytes']+=1;continue
  records.append(dict(source=p['image'],source_sha256=hashlib.sha256(Path(p['image']).read_bytes()).hexdigest(),owner=i,before=b['content'],candidate=c,reason=reason))
 for sub,data,ext in [('raw',patch(rb,re),'json'),('markdown',patch(md,me),'md')]:
  target=O/'generator_predictions'/sub/(p['id']+'.'+ext);original=src/sub/target.name
  if data==original.read_bytes():os.link(original,target)
  else:target.write_bytes(data)
(O/'inputs.json').write_text(json.dumps(dict(inputs=str(src))));(O/'census.json').write_text(json.dumps(dict(pages=len(pages),counts=counts,records=records,HTTP=0,seconds=time.monotonic()-start),ensure_ascii=False,indent=2));print(dict(counts),len(records))
