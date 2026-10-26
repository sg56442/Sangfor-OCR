"""Extend unowned risk band vertically over adjacent source glyph rows, not answers."""
import cv2,numpy as np
from prose_geometry_0141_v2 import intersection

def expand(im,box,native):
 if any(intersection(box,b['bbox'])>0 for b in native):return box,dict(reason='native_context_already_closed')
 w,h=im.size;x,y,X,Y=[box[k]*[w,h,w,h][k] for k in range(4)];gray=np.array(im.convert('L'));n,_,st,_=cv2.connectedComponentsWithStats((gray<160).astype('uint8'),8)
 near=[a for a in st[1:] if 3<=a[3]<=40 and 2<=a[2]<=40 and a[4]>=5 and x-40<=a[0]<=X+40 and y<=a[1]+a[3] and a[1]<=Y]
 if not near:return box,dict(reason='no_glyph_height')
 height=float(np.median([a[3] for a in near]));cs=[a for a in st[1:] if 3<=a[3]<=40 and 2<=a[2]<=40 and a[4]>=5 and a[0]>=x-height and a[0]+a[2]<=X+height]
 lo,hi=y,Y
 for _ in range(len(cs)+1):
  hit=[a for a in cs if a[1]<=hi+2*height and a[1]+a[3]>=lo-2*height]
  if not hit:break
  a,b=min(v[1] for v in hit),max(v[1]+v[3] for v in hit)
  if a>=lo and b<=hi:break
  lo=min(lo,a);hi=max(hi,b)
 hit=[a for a in cs if a[1]>=lo and a[1]+a[3]<=hi]
 if not hit:return box,dict(reason='no_extension')
 rect=[max(0,min(a[0] for a in hit)-3),max(0,lo-3),min(w,max(a[0]+a[2] for a in hit)+3),min(h,hi+3)]
 rect=[int(v) for v in rect]
 return [rect[0]/w,rect[1]/h,rect[2]/w,rect[3]/h],dict(reason='source_connected_row_extent',median_glyph_height=height,rect=rect,original_box=box)
