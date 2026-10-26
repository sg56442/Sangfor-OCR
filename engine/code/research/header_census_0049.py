"""Diagnostic native-only risk census. Never edits or accepts a span."""
import argparse,json,re,hashlib,time
from pathlib import Path
from PIL import Image
from table_mechanisms import grids

def risks(markup):
 out=[]
 for g in grids(markup):
  if g['conflicts'] or g['holes']:continue
  cells=g['cells']; at={(r,c):x for x in cells for r in range(x['row'],x['row']+x['rowspan']) for c in range(x['col'],x['col']+x['colspan'])}
  for h in cells:
   r,c=h['row'],h['col']
   if not h['text'].strip() or h['colspan']!=1 or h['rowspan']!=1:continue
   blank=at.get((r,c+1))
   if not blank or blank['text'].strip() or blank['colspan']!=1 or blank['row']!=r:continue
   parent=next((p for p in cells if p['row']<r and p['row']+p['rowspan']==r and p['col']<=c and p['col']+p['colspan']>=c+2),None)
   if not parent:continue
   siblings=[s for s in cells if s['row']==r and s['colspan']==2 and s['text'].strip() and parent['col']<=s['col'] and s['col']+2<=parent['col']+parent['colspan']]
   for s in siblings:
    body=[]
    for y in range(r+1,g['rows']):
     pair=[at.get((y,k)) for k in (c,c+1,s['col'],s['col']+1)]
     if any(x is None or x['rowspan']!=1 or x['colspan']!=1 for x in pair):body=[];break
     ts=[x['text'].strip() for x in pair]
     num=lambda t:bool(re.fullmatch(r'[−+\-]?\d+(?:[.,]\d+)?',t))
     sym=lambda t:bool(re.fullmatch(r'[A-Za-z]{1,3}|[*†‡]{1,3}',t))
     if not(num(ts[0]) and sym(ts[1]) and num(ts[2]) and sym(ts[3])):body=[];break
     body.append(ts)
    if len(body)>=3:out.append(dict(header=h,blank=blank,parent=parent,sibling=s,body=body,decision='ABSTAIN_SOURCE_PARENT_NOT_PROVEN'))
 return out
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--manifest',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=False);start=time.monotonic();sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();pages=json.load(open(a.manifest));rows=[];tables=0;bindings=[]
 for pi,p in enumerate(pages):
  rp=Path(a.inputs)/'raw'/(p['id']+'.json');raw=json.load(open(rp));bindings.append([sha(rp)])
  for owner,b in enumerate(raw['blocks']):
   if b['type']!='table':continue
   tables+=1;rr=risks(b.get('content') or '')
   if not rr:continue
   i=len(rows);im=Image.open(p['image']).convert('RGB');w,h=im.size;im.crop(tuple(v*s for v,s in zip(b['bbox'],[w,h,w,h]))).rotate(b.get('angle',0),expand=True).save(o/f'table_{i}.png');(o/f'before_{i}.html').write_text(b['content']);rows.append(dict(manifest_index=pi,owner=owner,source=p['image'],source_sha256=sha(p['image']),raw=str(rp),raw_sha256=sha(rp),risk=rr))
 result=dict(pages=len(pages),tables=tables,risk_owners=len(rows),selected=0,HTTP=0,wall_seconds=time.monotonic()-start,rows=rows,input_hashes=bindings,manifest_sha256=sha(a.manifest),script_sha256=sha(__file__))
 (o/'census.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print({k:v for k,v in result.items() if k not in ('rows','input_hashes')})
