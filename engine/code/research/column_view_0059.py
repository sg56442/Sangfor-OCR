"""Whole-parent right expansion to persistent physical gutter; no source IDs."""
import numpy as np,cv2
from boundary_view_0055 import detect
cv2.setNumThreads(2)
def measure(im,b):
 w,h=im.size;bb=b['bbox'];box=[round(v*s) for v,s in zip(bb,[w,h,w,h])];x,y,u,v=box
 if b.get('angle',0) or u<=x or v<=y or (v-y)/(u-x)<8 or bb[2]-bb[0]>.12 or bb[3]-bb[1]<.3:return None
 a,box,hits=detect(im,bb);right=[z['box'] for z in hits if 'right' in z['sides']];ys=sorted((z[1]+z[3])/2 for z in right);bands=[]
 for yy in ys:
  if not bands or yy-bands[-1]>8:bands.append(yy)
 ink=a[y:v]<180;end=None;count=0
 # Persistent all-parent-height whitespace prevents choosing a gap inside one short word.
 for xx in range(u,min(w,u+round(.25*w))):
  empty=int(ink[:,xx].sum())<=max(1,round(.001*(v-y)));count=count+1 if empty else 0
  if count>=4:end=xx+1;break
 if end is None:return dict(box=box,right_crossing=len(right),baseline_bands=len(bands),risk=False,reason='no_persistent_gutter',expanded_box=box)
 risk=len(bands)>=3 and end-u>=max(4,round(.1*(u-x)))
 return dict(box=box,right_crossing=len(right),baseline_bands=len(bands),risk=risk,reason='crossing_glyph_groups_to_persistent_gutter' if risk else 'no_multiple_clipped_glyph_baselines',expanded_box=[x,y,max(u,end),v],seam='4columns ink<=.001height; searchmax.25pagewidth; retain fullparent')
