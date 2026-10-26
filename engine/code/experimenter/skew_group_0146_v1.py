"""Input-only single-column short-row overlap and source baseline skew risk."""
import math
import numpy as np
import cv2
cv2.setNumThreads(1)
def risk(im,blocks):
 text=[(i,b) for i,b in enumerate(blocks) if b.get('type')=='text' and isinstance(b.get('content'),str) and len(b['content'].strip())>=4 and b.get('angle',0)==0]
 if len(text)<12:return dict(accepted=False,reason='too_few_text_rows')
 if any('\\' in b['content'] for _,b in text):return dict(accepted=False,reason='mixed_math')
 bs=[b['bbox'] for _,b in text]
 if any(len(b)!=4 or not all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in b) or b[2]<=b[0] or b[3]<=b[1] for b in bs):return dict(accepted=False,reason='invalid_bbox')
 if max(b[0] for b in bs)-min(b[0] for b in bs)>.08:return dict(accepted=False,reason='multiple_columns_or_indents')
 if np.median([b[3]-b[1] for b in bs])>.04:return dict(accepted=False,reason='not_short_rows')
 seq=sorted(text,key=lambda x:x[1]['bbox'][1]);overlap=[]
 for (i,a),(j,b) in zip(seq,seq[1:]):
  a=a['bbox'];b=b['bbox'];dy=min(a[3],b[3])-max(a[1],b[1]);frac=dy/min(a[3]-a[1],b[3]-b[1]);dx=min(a[2],b[2])-max(a[0],b[0])
  if .05<=frac<=.4 and dx>=.7*min(a[2]-a[0],b[2]-b[0]):overlap.append([i,j,frac])
 if len(overlap)<3:return dict(accepted=False,reason='no_repeated_overlap',overlap=overlap)
 bbox=[min(b[0] for b in bs),min(b[1] for b in bs),max(b[2] for b in bs),max(b[3] for b in bs)]
 for b in blocks:
  if b['type'] not in ['table','equation','image','image_block','chart']:continue
  x,y,X,Y=b['bbox'];dx=min(X,bbox[2])-max(x,bbox[0]);dy=min(Y,bbox[3])-max(y,bbox[1])
  if dx>0 and dy>0:return dict(accepted=False,reason='mixed_visual_region')
 w,h=im.size;rect=[round(v*s) for v,s in zip(bbox,[w,h,w,h])];crop=im.crop(rect);gray=np.array(crop.convert('L'));edges=cv2.Canny(gray,60,160);lines=cv2.HoughLinesP(edges,1,np.pi/180,40,minLineLength=max(80,crop.width//7),maxLineGap=20);angles=[]
 if lines is not None:
  for x,y,X,Y in lines.reshape(-1,4):
   if X==x:continue
   ang=math.degrees(math.atan((Y-y)/(X-x)))
   if abs(ang)<=12:angles.append(ang)
 median=float(np.median(angles)) if angles else 0.;mad=float(np.median(np.abs(np.array(angles)-median))) if angles else 0.
 ok=len(angles)>=6 and 2<=abs(median)<=12 and mad<=2
 return dict(accepted=bool(ok),reason='overlap_with_source_skew' if ok else 'source_skew_not_supported',indices=[i for i,b in seq],bbox=bbox,rect=rect,overlap=overlap,lines=len(angles),median_angle=median,mad=mad,view='complete single-column native text group union; no per-row padding/deskew/answer editing')
