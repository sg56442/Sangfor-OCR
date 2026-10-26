"""Diagnostic gate: native-empty, physically ruled cell with repeated text-size ink bands."""
import cv2,numpy as np
from spacing_gate_0042 import grid
from cell_lines_0073_v2 import runs
cv2.setNumThreads(1)
def candidates(im,b):
 g=grid(b.get('content') or '')
 if not g:return []
 cells=[c for c in g['cells'] if not c['text'].strip() and c.get('rowspan',1)==1 and c.get('colspan',1)==1]
 if not cells:return []
 w,h=im.size;box=b['bbox']
 if len(box)!=4 or not all(np.isfinite(box)) or not(0<=box[0]<box[2]<=1 and 0<=box[1]<box[3]<=1):return []
 crop=im.crop(tuple(v*s for v,s in zip(box,[w,h,w,h]))).convert('RGB').rotate(b.get('angle',0),expand=True);a=np.array(crop.convert('L'));H,W=a.shape;coords=[]
 for t in [180,210]:
  ink=(a<t).astype('uint8');hl=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(30,W//2)),np.uint8));vl=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((max(30,H//2),1),np.uint8));ys=[(s+e)//2 for s,e in runs(hl.sum(1)>.7*W)];xs=[(s+e)//2 for s,e in runs(vl.sum(0)>.5*H)]
  if len(ys)!=g['rows']+1 or len(xs)!=g['width']+1:return []
  coords.append((xs,ys))
 if any(abs(x-y)>3 for aa,bb in zip(*coords) for x,y in zip(aa,bb)):return []
 xs,ys=coords[0];out=[]
 for c in cells:
  box=[xs[c['col']]+2,ys[c['row']]+2,xs[c['col']+1]-2,ys[c['row']+1]-2];v=crop.crop(box);m=(np.array(v.convert('L'))<180).astype('uint8');hh,ww=m.shape
  bands=[(s,e) for s,e in runs(m.sum(1)>max(3,ww*.01)) if 3<=e-s<=hh*.15]
  n,l,stats,_=cv2.connectedComponentsWithStats(m,8);good=[s for s in stats[1:] if s[4]>=8 and 3<=s[2]<=ww*.12 and 3<=s[3]<=hh*.12];ratio=sum(int(s[4]) for s in good)/max(1,int(m.sum()))
  if len(bands)<6 or len(good)<30 or ratio<.85:continue
  out.append(dict(row=c['row'],col=c['col'],box=box,bands=bands,components=len(good),component_coverage=ratio,crop=v))
 return out
