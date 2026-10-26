"""Input-only boundary signal and whole-owner white-seam expansion. No OCR/GT."""
import cv2,numpy as np

def detect(im,bbox):
 a=np.asarray(im.convert('L'));h,w=a.shape;n,lab,st,ct=cv2.connectedComponentsWithStats((a<180).astype('uint8'),8);b=[round(v*s) for v,s in zip(bbox,[w,h,w,h])];hits=[]
 for x,y,cw,ch,ar in st[1:]:
  if not(3<=cw<=100 and 3<=ch<=100 and ar>=8 and .12<=cw/ch<=8):continue
  x,y,cw,ch=map(int,(x,y,cw,ch));u=x+cw;v=y+ch
  if not(x<b[2] and u>b[0] and y<b[3] and v>b[1]):continue
  sides=[]
  for yes,s in [(x<b[0]-1 and u>b[0]+1,'left'),(x<b[2]-1 and u>b[2]+1,'right'),(y<b[1]-1 and v>b[1]+1,'top'),(y<b[3]-1 and v>b[3]+1,'bottom')]:
   if yes:sides.append(s)
  if sides:hits.append(dict(box=[x,y,u,v],sides=sides))
 return a,b,hits

def expand(a,b,hits):
 h,w=a.shape;ink=a<180;v=b.copy();dirs={s for q in hits for s in q['sides']}
 for s in ['top','bottom','left','right']:
  if s not in dirs:continue
  axis={'left':0,'top':1,'right':2,'bottom':3}[s];vals=[q['box'][axis] for q in hits if s in q['sides']];low=s in ['top','left'];start=min(vals) if low else max(vals);limit=0 if low else (h if s=='bottom' else w);step=-1 if low else 1;count=0;end=start
  for p in range(start,limit,step):
   if s in ['top','bottom']:empty=not ink[min(h-1,max(0,p)),v[0]:v[2]].any()
   else:empty=not ink[v[1]:v[3],min(w-1,max(0,p))].any()
   count=count+1 if empty else 0;end=p
   if count>=3:break
  v[axis]=min(v[axis],max(0,end)) if low else max(v[axis],min(limit,end+1))
 return v,dict(directions=sorted(dirs),original_box=b,expanded_box=v,white_seam='3 consecutive full-cross-section rows/columns without gray<180; retain entire owner; no masking',context_allowed=True)
