"""Pixel-only closed-box risk. Diagnostic gate, not proof of text fidelity."""
import cv2,numpy as np,math

def view(im,b):
 w,h=im.size;x0,y0,x1,y1=b['bbox'];r=[math.floor(x0*w),math.floor(y0*h),math.ceil(x1*w),math.ceil(y1*h)]
 # Expand outwards to a complete white seam; no pixels removed.
 a=np.asarray(im.convert('RGB'));gray=cv2.cvtColor(a,cv2.COLOR_RGB2GRAY)
 maxpad=max(8,round(min(w,h)*.025))
 for k in range(4):
  found=False
  for d in range(maxpad+1):
   t=r.copy();t[k]+=(-d if k<2 else d)
   if t[0]<0 or t[1]<0 or t[2]>w or t[3]>h:break
   band=gray[t[1]:t[3],max(0,t[0]-1):t[0]+1] if k==0 else gray[max(0,t[1]-1):t[1]+1,t[0]:t[2]] if k==1 else gray[t[1]:t[3],t[2]-1:min(w,t[2]+1)] if k==2 else gray[t[3]-1:min(h,t[3]+1),t[0]:t[2]]
   if band.size and (band>235).mean()>.995:r=t;found=True;break
  if not found:return dict(accepted=False,reason='no_complete_white_seam',rect=r)
 crop=gray[r[1]:r[3],r[0]:r[2]];mask=(crop<210).astype('uint8')*255
 contours,_=cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE);boxes=[]
 for c in contours:
  x,y,bw,bh=cv2.boundingRect(c);area=cv2.contourArea(c)
  if bw<crop.shape[1]*.15 or bh<12 or bw/bh<1.4 or bw/bh>20 or area/(bw*bh)<.75:continue
  if bw*bh>crop.size*.65:continue
  inner=mask[y+4:y+bh-4,x+4:x+bw-4]
  n,_,stats,_=cv2.connectedComponentsWithStats(inner)
  glyph=sum(1 for sx,sy,sw,sh,sa in stats[1:] if sh>=4 and sw>=2 and sa>=5 and sh<bh*.85 and sw<bw*.25)
  if glyph<3:continue
  rect=[x,y,x+bw,y+bh]
  if any(abs(x-t[0])+abs(y-t[1])+abs(x+bw-t[2])+abs(y+bh-t[3])<20 for t in boxes):continue
  boxes.append(rect)
 boxes.sort(key=lambda x:(x[1],x[0]));accept=b['type']=='image' and b.get('angle',0)==0 and len(boxes)>=2
 return dict(accepted=accept,reason='multiple_complete_closed_text_boxes' if accept else 'no_image_multibox_support',rect=r,boxes=boxes,not_a_source_correctness_proof=True)
