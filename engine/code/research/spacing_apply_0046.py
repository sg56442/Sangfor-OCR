"""Whole-owner assembly: accumulate per page; exact UTF-8 LF/CRLF binding only."""
import argparse,json,os,hashlib,re
from pathlib import Path
from PIL import Image
from spacing_geometry_0042 import bind
from spacing_gate_0042 import grid

def span(md,old,new):
 """Only newline representation may differ. Never fuzzy text/cell matching."""
 token=old.encode('utf-8').replace(b'\r\n',b'\n')
 pattern=b'\r?\n'.join(re.escape(v) for v in token.split(b'\n'))
 matches=list(re.finditer(pattern,md));assert len(matches)==1,'Markdown owner binding not unique'
 m=matches[0];original=m.group();ends=re.findall(b'\r?\n',original)
 if not ends:ends=re.findall(b'\r?\n',md)
 assert len(set(ends))<=1,'Mixed newline owner context ambiguous'
 newline=ends[0] if ends else b'\n'
 replacement=new.encode('utf-8').replace(b'\r\n',b'\n').replace(b'\n',newline)
 return m.start(),m.end(),replacement

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--manifest',required=True);ap.add_argument('--bundle',required=True);ap.add_argument('--out',required=True);ap.add_argument('--arm',choices=['generator','selector'],required=True);a=ap.parse_args()
 src=Path(a.inputs);out=Path(a.out);pages=json.load(open(a.manifest));bundle=json.load(open(a.bundle));keys=[(r['manifest_index'],r['owner']) for r in bundle];assert len(keys)==len(set(keys)),'Duplicate owner forbidden'
 bundle=sorted(bundle,key=lambda r:(r['manifest_index'],r['owner']));records=[];pending={}
 for r in bundle:
  p=pages[r['manifest_index']];rp=src/'raw'/(p['id']+'.json');original=json.load(rp.open());old=original['blocks'][r['owner']]['content'];new=r['html'];decision=dict(accepted=False,reason='input_owner_changed');bound=hashlib.sha256(old.encode()).hexdigest()==r['before_sha256']
  if bound:
   assert hashlib.sha256(Path(p['image']).read_bytes()).hexdigest()==r['source_sha256'];b=original['blocks'][r['owner']]
   if old==new:decision=dict(accepted=True,reason='identity')
   else:
    im=Image.open(p['image']).convert('RGB');w,h=im.size;im=im.crop(tuple(v*s for v,s in zip(b['bbox'],[w,h,w,h]))).rotate(b.get('angle',0),expand=True);decision=bind(im,old,new)
  valid=grid(new) is not None;apply=bound and valid and (a.arm=='generator' or decision['accepted']) and old!=new
  if apply:
   key=r['manifest_index']
   if key not in pending:pending[key]=dict(raw=original,md=(src/'markdown'/(p['id']+'.md')).read_bytes(),edits=[])
   item=pending[key]
   try:s,e,text=span(item['md'],old,new)
   except AssertionError:decision=dict(accepted=False,reason='markdown_owner_binding_ambiguous');apply=False
   else:
    assert not any(s<z[1] and e>z[0] for z in item['edits']),'Overlapping owner spans'
    item['edits'].append((s,e,text));item['raw']['blocks'][r['owner']]['content']=new
  records.append(dict(manifest_index=r['manifest_index'],owner=r['owner'],decision=decision,applied=apply,valid_grid=valid))
 out.mkdir(parents=True,exist_ok=False)
 for sub in ['raw','markdown']:
  (out/sub).mkdir()
  for p in (src/sub).iterdir():
   if p.is_file():os.link(p,out/sub/p.name)
 for key,item in pending.items():
  if not item['edits']:continue
  md=item['md']
  for s,e,text in sorted(item['edits'],reverse=True):md=md[:s]+text+md[e:]
  for sub,ext,data in [('raw','json',json.dumps(item['raw'],ensure_ascii=False,indent=2).encode()),('markdown','md',md)]:
   target=out/sub/(pages[key]['id']+'.'+ext);target.unlink();target.write_bytes(data)
 (out/'receipt.json').write_text(json.dumps(dict(arm=a.arm,records=records,changed=sum(r['applied'] for r in records),files=sum(1 for sub in ['raw','markdown'] for p in (out/sub).iterdir()),HTTP=0),indent=2));print([(r['manifest_index'],r['decision']['reason'],r['applied']) for r in records])
if __name__=='__main__':main()
