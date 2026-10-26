"""Source-only contiguous full-width partition. Diagnostic, not deployed."""
import numpy as np,cv2

def bands(v):
 z=np.flatnonzero(np.diff(np.r_[False,v,False].astype(int)));return list(zip(z[::2].tolist(),z[1::2].tolist()))
def geometry(im):
 a=np.array(im.convert('L'));h,w=a.shape;m=(a<180).astype('uint8');horiz=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((1,max(30,w//2)),np.uint8));ink=m-horiz
 gaps=bands(ink.sum(0)<=max(1,h*.002));gg=[(s,e) for s,e in gaps if .01*w<s<.18*w and e-s>=3]
 if not gg:return {'admitted':False,'reason':'no_first_column_gutter'}
 s,e=min(gg,key=lambda q:q[0]);x=(s+e)//2
 anchors=bands(ink[:,:x].sum(1)>0);blank=bands(ink.sum(1)<=max(1,w*.001));opts=[]
 for y,z in anchors:
  if not .30*h<y<.70*h:continue
  prior=[(s,e) for s,e in blank if e<=y and y-e<=max(24,h*.04) and e-s>=3]
  if prior:
   ss,ee=max(prior,key=lambda q:q[1]);opts.append((abs(y-h/2), (ss+ee)//2,y))
 if not opts:return {'admitted':False,'reason':'no_fullwidth_blank_before_anchor','gutter':x}
 _,cut,anchor=min(opts)
 return {'admitted':True,'gutter':x,'cut':cut,'anchor_y':anchor,'size':[w,h],'views':[[0,0,w,cut],[0,cut,w,h]],'scope':'source geometric anchor only; semantic parent uniqueness unproved'}
