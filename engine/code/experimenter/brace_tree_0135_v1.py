"""Provisional source-only nested-brace text-tree risk; no character guessing."""
import cv2,numpy as np
from boxed_diagram_0133_v1 import view as rectangle

def risk(im,blocks,i):
 b=blocks[i];q=rectangle(im,b);r=q['rect'];q=dict(rect=r,accepted=False,reason='not_upright_image')
 if b['type']!='image' or b.get('angle',0)!=0:return q
 a=np.asarray(im.crop(r).convert('L'));ink=(a<90).astype('uint8');H,W=ink.shape;n,labels,stats,_=cv2.connectedComponentsWithStats(ink);braces=[];body=ink.copy()
 for k,(x,y,w,h,s) in enumerate(stats[1:],1):
  if h>=H*.25 and 4<=w<=W*.08 and h/w>=7 and x+w<W*.45 and s/(w*h)<.5:
   braces.append([int(x),int(y),int(x+w),int(y+h)]);body[labels==k]=0
 active=body.sum(axis=1)>=max(4,W*.015);runs=[];start=None
 for y,on in enumerate([*active,False]):
  if on and start is None:start=y
  if not on and start is not None:
   if y-start>=3:runs.append([start,y])
   start=None
 xs=[]
 for x in sorted(b[0] for b in braces):
  if not xs or x-xs[-1]>W*.05:xs.append(x)
 ok=len(xs)>=2 and len(runs)>=5
 q.update(braces=braces,brace_x_groups=xs,text_bands=runs,accepted=ok,reason='nested_left_braces_and_multiple_text_bands' if ok else 'insufficient_brace_tree_support');return q
