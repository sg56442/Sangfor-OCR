"""v1 order with finite geometry, disjoint-scope and source gutter proof guards."""
import math
import numpy as np
from column_bridge_0147_v1 import proposals as propose,apply

def proposals(bs,im):
 for b in bs:
  bb=b.get('bbox')
  if not isinstance(bb,list) or len(bb)!=4 or not all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in bb) or bb[0]>=bb[2] or bb[1]>=bb[3]:return []
 qs=propose(bs)
 if any(max(a['lo'],b['lo'])<=min(a['hi'],b['hi']) for i,a in enumerate(qs) for b in qs[i+1:]):return []
 accepted=[];w,h=im.size
 for q in qs:
  y=bs[q['image']]['bbox'][1];Y=bs[q['image']]['bbox'][3];top=min(bs[i]['bbox'][1] for i in q['old']);bottom=max(bs[i]['bbox'][3] for i in q['old']);proof=[]
  for (_,r),(l,_) in zip(q['columns'],q['columns'][1:]):
   a=r+.25*(l-r);b=l-.25*(l-r)
   for c,d in [(top,y),(Y,bottom)]:
    rect=[round(a*w),round(c*h),round(b*w),round(d*h)]
    if rect[2]-rect[0]<2 or rect[3]-rect[1]<4:break
    pixels=np.array(im.crop(rect).convert('L'));ink=float((pixels<160).mean());proof.append(dict(rect=rect,dark_fraction=ink))
  if len(proof)==2*(len(q['columns'])-1) and all(x['dark_fraction']<=.08 for x in proof):accepted.append(dict(**q,gutter_proof=proof))
 return accepted
