"""Exact brace-view rectangle, reusing page grayscale and omitting unused boxes.

The original brace risk uses only rectangle['rect'] from the boxed-diagram view.
Its later closed-box extraction has no effect on that rectangle. The page image
is immutable during each census; grayscale exists only on that live object.
"""
import math
import cv2
import numpy as np

def rectangle(im,b):
 w,h=im.size;x0,y0,x1,y1=b['bbox'];r=[math.floor(x0*w),math.floor(y0*h),math.ceil(x1*w),math.ceil(y1*h)]
 gray=getattr(im,'_rsi_brace_grayscale_v1',None)
 if gray is None:
  gray=cv2.cvtColor(np.asarray(im.convert('RGB')),cv2.COLOR_RGB2GRAY)
  im._rsi_brace_grayscale_v1=gray
 maxpad=max(8,round(min(w,h)*.025))
 for k in range(4):
  found=False
  for d in range(maxpad+1):
   t=r.copy();t[k]+=(-d if k<2 else d)
   if t[0]<0 or t[1]<0 or t[2]>w or t[3]>h:break
   band=gray[t[1]:t[3],max(0,t[0]-1):t[0]+1] if k==0 else gray[max(0,t[1]-1):t[1]+1,t[0]:t[2]] if k==1 else gray[t[1]:t[3],t[2]-1:min(w,t[2]+1)] if k==2 else gray[t[3]-1:min(h,t[3]+1),t[0]:t[2]]
   if band.size and (band>235).mean()>.995:r=t;found=True;break
  if not found:return dict(rect=r)
 return dict(rect=r)
