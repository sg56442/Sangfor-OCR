"""Fresh manifest/input panel validation. No old observations or GT inputs."""
import argparse,json,sys,hashlib,time,collections,os
from pathlib import Path
from PIL import Image
from panel_flow_0109_v3 import census_page
from panel_group_gate_0109_v1 import admit
from compose_panels_0108_v2 import select
from finite_request_identity_0101_v1 import prepare,pix,key
R=Path(__file__).resolve().parents[2]
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',required=True);ap.add_argument('--inputs',required=True);ap.add_argument('--out',required=True);ap.add_argument('--stage',choices=['scan','text','compose'],required=True);a=ap.parse_args();O=Path(a.out).resolve();B=Path(a.inputs).resolve();O.mkdir(parents=True,exist_ok=True)
 if a.stage=='scan':
  assert not (O/'census.json').exists();records=[];bindings=[];t=time.monotonic()
  for page in load(a.manifest):
   rp=B/'raw'/(page['id']+'.json');mp=B/'markdown'/(page['id']+'.md');raw=load(rp);im=Image.open(page['image']).convert('RGB');rh,sh=sha(rp),sha(page['image']);bindings.append([str(rp),rh,page['image'],sh,str(mp),sha(mp)])
   for q in census_page(im,raw):records.append(dict(q,ordinal=len(records),source=page['image'],source_sha256=sh,raw=str(rp),raw_sha256=rh))
  save(O/'census.json',dict(pages=len(bindings),records=records,bindings=bindings,seconds=time.monotonic()-t));save(O/'budget.json',dict(maximum=24,reserved=0,by_source={},identities=[],by_candidate={},denials=[]))
  req=[]
  for c in records:
   if not c['eligible'] or c['normal']:continue
   p=prepare(Image.open(c['source']).convert('RGB').crop(c['rect']),'[layout]');req.append(dict(ordinal=c['ordinal'],rect=c['rect'],task='[layout]',identity_key=key(p.size,pix(p),'[layout]'),prepared_size=list(p.size),prepared_pixel_sha256=pix(p),normal=False))
  save(O/'plan_layout.json',dict(requests=req));print('census',len(bindings),len(records),'layout',len(req),flush=True)
 elif a.stage=='text':
  c=load(O/'census.json')['records'];obs=sum([load(p) for p in O.glob('gpu*_attemptlayout/results.json')],[]);req=[];gate=[]
  for r in obs:
   q=c[r['ordinal']];view=Image.open(q['source']).convert('RGB').crop(q['rect']);ok,why=admit(r,q,view);gate.append(dict(ordinal=q['ordinal'],eligible=ok,evidence=why))
   if ok:
    p=prepare(view,'text');req.append(dict(ordinal=q['ordinal'],rect=q['rect'],task='text',identity_key=key(p.size,pix(p),'text'),prepared_size=list(p.size),prepared_pixel_sha256=pix(p),normal=False))
  save(O/'layout_binding.json',gate);save(O/'plan_recognition.json',dict(requests=req));print('text',len(req),flush=True)
 else:
  c=load(O/'census.json')['records'];obs=sum([load(p) for p in O.glob('gpu*/results.json')],[]);edits=collections.defaultdict(list);decisions=[];g={x['ordinal']:x['eligible'] for x in load(O/'layout_binding.json')}
  for q in c:
   decisions.append(dict(ordinal=q['ordinal'],configured=True,triggered=bool(q['eligible'] and not q['normal']),applied=False,consumed=False,selected=False,scored=False,reason='normal_identity' if q['normal'] else q['relation_reason']))
  for r in obs:
   if r['task']!='text':continue
   q=c[r['ordinal']];raw=load(q['raw']);md=(B/'markdown'/Path(q['raw']).with_suffix('.md').name).read_text();edit,d=select(q,r,raw,md)
   if not g.get(q['ordinal']):edit=None;d.update(selected=False,reason='layout_fallback')
   decisions.append(d)
   if edit:edits[q['raw']].append(dict(edit,ordinal=q['ordinal'],source=q['source']))
  D=O/'candidate/predictions';assert not D.exists()
  for sub in ['raw','markdown']:(D/sub).mkdir(parents=True)
  changed=[]
  for rp in sorted((B/'raw').glob('*.json')):
   mp=B/'markdown'/rp.with_suffix('.md').name;rows=edits.get(str(rp),[])
   if not rows:
    os.link(rp,D/'raw'/rp.name);os.link(mp,D/'markdown'/mp.name);continue
   raw=load(rp);md=mp.read_text();new=[]
   for i,b in enumerate(raw['blocks']):
    new.append(b)
    for q in sorted([z for z in rows if z['owner']==i],key=lambda z:(z['rect'][1],z['rect'][0])):
     w,h=Image.open(q['source']).size;new.append(dict(type='text',bbox=[v/(w if j%2==0 else h) for j,v in enumerate(q['rect'])],angle=0,content=q['text'],merge_prev=False,source_panel_parent_index=i,source_panel_relation='transcription_inside_preserved_image'))
   raw['blocks']=new;groups=collections.defaultdict(list)
   for q in sorted(rows,key=lambda z:(z['owner'],z['rect'][1],z['rect'][0])):groups[q['anchor']].append(q['text'])
   for anchor,parts in groups.items():assert md.count(anchor)==1;md=md.replace(anchor,'\n\n'.join(parts)+'\n\n'+anchor,1)
   save(D/'raw'/rp.name,raw);(D/'markdown'/mp.name).write_text(md);changed.append(rp.stem)
  for arm,src in [('baseline',B),('selector',D)]:
   for sub,ext in [('raw','.json'),('markdown','.md')]:
    dest=O/'paired/subset'/arm/sub;dest.mkdir(parents=True)
    for n in changed:os.link(src/sub/(n+ext),dest/(n+ext))
  save(O/'selection.json',dict(decisions=decisions,edits=edits,changed_pages=changed,actual_HTTP=load(O/'budget.json')['reserved']));print('selected',sum(map(len,edits.values())),flush=True)
if __name__=='__main__':main()
