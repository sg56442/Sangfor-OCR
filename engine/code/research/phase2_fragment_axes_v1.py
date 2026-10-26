"""Source-only common interior whitespace separators across upper/lower value rows."""
import numpy as np,cv2
from PIL import Image
from table_mechanisms import runs
from phase2_fragment_proposal_v2 import bands

def verify(p,raw):
 with Image.open(p['image']) as im:
  im=im.convert('RGB');w,h=im.size
  box=lambda b:[round(v*(w if k%2==0 else h)) for k,v in enumerate(b)]
  rb=box(raw['blocks'][p['right']]['bbox']);ub=box(raw['blocks'][p['upper']]['bbox'])
  # Same global x support for both groups; excludes labels and retains dash placeholders.
  allrows=[]
  for name,y1,y2 in [('upper',ub[1],ub[3]),('lower',rb[1],rb[3])]:
   crop=im.crop((rb[0],y1,rb[2],y2));a=np.asarray(crop.convert('L'))<180
   a &= ~cv2.morphologyEx(a.astype('uint8'),cv2.MORPH_OPEN,np.ones((1,max(20,crop.width//2)),np.uint8)).astype(bool)
   for s,e in bands(crop):
    xs=runs(a[s:e].sum(0)>0);merged=[]
    for x,z in xs:
     if merged and x-merged[-1][1]<=max(3,(e-s)*.5):merged[-1][1]=z
     else:merged.append([x,z])
    if len(merged)==p['width']-1:allrows.append(dict(group=name,y=[y1+s,y1+e],segments=[[rb[0]+x,rb[0]+z] for x,z in merged]))
  lower=[r for r in allrows if r['group']=='lower'];upper=[r for r in allrows if r['group']=='upper']
  if len(lower)!=p['rows'] or len(upper)<2:return dict(accept=False,reason='insufficient_six_run_source_rows',rows=allrows)
  gaps=[]
  for k in range(p['width']-2):
   lo=max(r['segments'][k][1] for r in allrows);hi=min(r['segments'][k+1][0] for r in allrows);gaps.append([lo,hi])
  ok=all(hi-lo>=3 for lo,hi in gaps)
  return dict(accept=ok,reason='common_interior_whitespace_partition' if ok else 'interior_axis_conflict',rows=allrows,gaps=gaps,scope='source ink-run order and shared separators, not glyph semantic proof')
