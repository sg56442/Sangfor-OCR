"""Minimal child text insertion, fixed whole observed cohort; no scoring inputs."""
import sys,json,os,re,hashlib,collections,copy
from pathlib import Path
R=Path(__file__).resolve().parents[2];O=R/'code/experimenter/runs/text_witness_0108/v2';B=R/'runs/phase2_formula_label_B_v1/predictions'
def load(p):return json.loads(Path(p).read_text())
def norm(s):return ''.join(ch.casefold() for ch in s if ch.isalnum())
def select(c,r,raw,md):
 d=dict(ordinal=c['ordinal'],normal=c['normal'],configured=True,triggered=True,applied=r.get('applied',False),consumed=r.get('consumed',False),selected=False,scored=False)
 if r.get('status')!='CONSUMED' or not r.get('finished_normally'):return None,dict(d,reason='failed_or_length_limit')
 text=r['raw_answer'].strip()
 if not text or '<|' in text or '<table' in text or not any(z.isalnum() for z in text):return None,dict(d,reason='non_plain_text_response')
 if c['normal']:return None,dict(d,reason='existing_native_text_observation_no_duplicate',observation=text)
 if any(norm(text) in norm(b.get('content') or '') for b in raw['blocks'] if b.get('content')):return None,dict(d,reason='already_in_current_native')
 # Unique source-order anchor, never choose an ordering by metric.
 for j,b in enumerate(raw['blocks'][c['owner']+1:],c['owner']+1):
  s=b.get('content') or ''
  if len(s)>5 and md.count(s)==1:return dict(owner=c['owner'],text=text,anchor=s,anchor_index=j,rect=c['rect']),dict(d,selected=True,reason='complete_source_panel_child_unique_next_native_anchor',anchor_index=j)
 return None,dict(d,reason='no_unique_markdown_anchor')
def main():
 c=load(O/'census.json')['records'];obs=sum([load(p) for p in sorted(O.glob('gpu*/results.json'))],[]);decisions=[];edits=collections.defaultdict(list)
 for r in obs:
  q=c[r['ordinal']];raw=load(q['raw']);md=(B/'markdown'/Path(q['raw']).with_suffix('.md').name).read_text();edit,d=select(q,r,raw,md);decisions.append(d)
  if edit:edits[q['raw']].append(dict(**edit,ordinal=q['ordinal'],source=q['source']))
 D=O/'candidate/predictions';assert not D.exists()
 for sub in ['raw','markdown']:(D/sub).mkdir(parents=True)
 changed=[];identity=[]
 from PIL import Image
 for rp in sorted((B/'raw').glob('*.json')):
  mp=B/'markdown'/rp.with_suffix('.md').name;rows=edits.get(str(rp),[])
  if not rows:
   os.link(rp,D/'raw'/rp.name);os.link(mp,D/'markdown'/mp.name);identity.append(rp.stem);continue
  raw=load(rp);md=mp.read_text();new=[]
  for i,b in enumerate(raw['blocks']):
   new.append(b)
   for q in sorted([z for z in rows if z['owner']==i],key=lambda z:(z['rect'][1],z['rect'][0])):
    w,h=Image.open(q['source']).size;new.append(dict(type='text',bbox=[v/(w if j%2==0 else h) for j,v in enumerate(q['rect'])],angle=0,content=q['text'],merge_prev=False,source_panel_parent_index=i,source_panel_relation='transcription_inside_preserved_image'))
  raw['blocks']=new
  groups=collections.defaultdict(list)
  for q in sorted(rows,key=lambda z:(z['owner'],z['rect'][1],z['rect'][0])):groups[q['anchor']].append(q['text'])
  for anchor,parts in groups.items():assert md.count(anchor)==1;md=md.replace(anchor,'\n\n'.join(parts)+'\n\n'+anchor,1)
  (D/'raw'/rp.name).write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n');(D/'markdown'/mp.name).write_text(md);changed.append(rp.stem)
 for arm,src in [('baseline',B),('selector',D)]:
  for sub,ext in [('raw','.json'),('markdown','.md')]:
   dest=O/'paired/subset'/arm/sub;dest.mkdir(parents=True)
   for n in changed:os.link(src/sub/(n+ext),dest/(n+ext))
 (O/'selection.json').write_text(json.dumps(dict(decisions=decisions,edits=dict(edits),changed_pages=changed,unchanged_pages=len(identity),actual_HTTP=load(O/'budget.json')['reserved']),ensure_ascii=False,indent=2));print('changedpages',len(changed),'selected',sum(d['selected'] for d in decisions))
if __name__=='__main__':main()
