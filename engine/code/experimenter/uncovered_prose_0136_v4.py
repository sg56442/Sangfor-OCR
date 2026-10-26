"""Diagnostic current-pixel uncovered glyph-band census; no score/identity predicates."""
import cv2,numpy as np,json,sys
from PIL import Image
from pathlib import Path

def detect(im,blocks):
 scale=1;w=round(im.width*scale);h=round(im.height*scale);a=np.asarray(im.convert('L').resize((w,h)));ink=(a<160).astype('uint8');covered=np.zeros_like(ink)
 for b in blocks:
  x,y,X,Y=b['bbox'];x,y,X,Y=int(x*w),int(y*h),int(np.ceil(X*w)),int(np.ceil(Y*h));covered[max(0,y-2):min(h,Y+2),max(0,x-2):min(w,X+2)]=1
 free=ink*(1-covered);n,lab,stats,_=cv2.connectedComponentsWithStats(free);glyph=np.zeros_like(ink)
 for k,(x,y,bw,bh,area) in enumerate(stats[1:],1):
  if 3<=bh<=40 and 2<=bw<=40 and area>=5 and .1<=bw/bh<=4:glyph[y:y+bh,x:x+bw][lab[y:y+bh,x:x+bw]==k]=1
 joined=cv2.dilate(glyph,np.ones((1,9),np.uint8));n,lab,stats,_=cv2.connectedComponentsWithStats(joined);rows=[]
 for x,y,bw,bh,area in stats[1:]:
  if bw>=60 and 3<=bh<=35 and glyph[y:y+bh,x:x+bw].sum()>=30:rows.append([int(x),int(y),int(x+bw),int(y+bh)])
 return dict(resized=[w,h],scale=scale,uncovered_bands=rows,uncovered_ink=int(free.sum()),native_covered_ink=int((ink*covered).sum()),note='Risk only; no text assertion, line/texture false positives require complete source audit.')
if __name__=='__main__':
 im=Image.open(sys.argv[1]);r=json.loads(Path(sys.argv[2]).read_text());d=detect(im,r['blocks']);Path(sys.argv[3]).write_text(json.dumps(d,indent=2));print(len(d['uncovered_bands']))
