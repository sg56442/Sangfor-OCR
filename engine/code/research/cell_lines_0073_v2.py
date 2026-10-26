"""Physical ruled-cell line recovery proposal; no GT or source identity."""
import re,cv2,numpy as np
from bs4 import BeautifulSoup
from spacing_gate_0042 import grid
cv2.setNumThreads(1)
def runs(a):
 z=np.flatnonzero(np.diff(np.r_[False,a,False].astype(int)));return [(int(s),int(e)) for s,e in zip(z[::2],z[1::2])]
def lexical(s):
 if any(x in s for x in ['<','>','$','\\','\n']):return False
 return bool((re.fullmatch(r'[\d. ]+',s) and s.count('.')>=2) or re.search(r'[A-Z]{3,}[a-z]{2,}',s))
def candidates(im,b):
 g=grid(b.get('content') or '')
 if not g:return []
 cells=g['cells'];risk=[(i,c) for i,c in enumerate(cells) if lexical(c['text'])]
 if not risk:return []
 w,h=im.size;box=[round(v*z) for v,z in zip(b['bbox'],[w,h,w,h])];crop=im.convert('RGB').crop(box).rotate(b.get('angle',0),expand=True);a=np.array(crop.convert('L'));H,W=a.shape;out=[]
 for th in [180,210]:
  ink=(a<th).astype('uint8');hor=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(30,W//4)),np.uint8));ver=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((max(30,H//3),1),np.uint8));xs=[(s+e)//2 for s,e in runs(ver.sum(0)>H*.35)]
  if not xs or xs[0]>10:xs.insert(0,0)
  if xs[-1]<W-10:xs.append(W-1)
  else:xs[-1]=W-1
  if xs[0]<10:xs[0]=0
  # A horizontal boundary must span a complete interval between physical column rails.
  valid=np.zeros(H,dtype=bool)
  for left,right in zip(xs,xs[1:]):valid|=(hor[:,left+3:right-2].sum(1)>.95*max(1,right-left-5))
  ys=[(s+e)//2 for s,e in runs(valid)]
  for arr,dim in [(ys,H),(xs,W)]:
   if not arr or arr[0]>4:arr.insert(0,0)
   if arr[-1]<dim-5:arr.append(dim-1)
  if len(xs)!=g['width']+1 or len(ys)!=g['rows']+1:return []
  if th==180:coords=(xs,ys)
  elif any(abs(x-y)>3 for a1,a2 in zip(coords,(xs,ys)) for x,y in zip(a1,a2)):return []
 xs,ys=coords
 for i,c in risk:
  x0,x1=xs[c['col']],xs[c['col']+c.get('colspan',1)];y0,y1=ys[c['row']],ys[c['row']+c.get('rowspan',1)];inner=crop.crop((x0+3,y0+3,x1-2,y1-2));ink=np.array(inner.convert('L'))<140;bands=[(s,e) for s,e in runs(ink.sum(1)>1) if e-s>=3]
  if not 2<=len(bands)<=4:continue
  out.append(dict(cell=i,text=c['text'],row=c['row'],col=c['col'],box=[x0+3,y0+3,x1-2,y1-2],bands=bands,crop=inner,tablebox=box,angle=b.get('angle',0)))
 return out
