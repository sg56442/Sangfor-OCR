"""Source whitespace separators across adjacent columns, from full-page pixels.
No strings, identifiers, GT or output reordering. Conservative rejection only.
"""
import numpy as np
from column_continuation_v1 import lines

def inspect(image,blocks,a,b):
 x,y=blocks[a]['bbox'],blocks[b]['bbox'];w,h=image.size
 ends=[lines(image,z)['lines'] for z in (x,y)];heights=[q[3]-q[1] for ls in ends for q in ls]
 if not heights:return dict(blocked=False,separators=[],reason='no_line_scale')
 scale=float(np.median(heights));minimum=1.5*scale
 left=max(0,round(x[0]*w));right=min(w,round(y[2]*w));top=max(0,round(y[1]*h));bottom=min(h,round(x[1]*h))
 if right<=left or bottom<=top:return dict(blocked=False,separators=[])
 # Full source interval between columns' starts, including intervening regions.
 raster=np.asarray(image.crop((left,top,right,bottom)).convert('L'));ink=raster<min(210,float(np.percentile(raster,90))-35)
 blank=np.flatnonzero(ink.sum(axis=1)<=max(1,(right-left)*.001));runs=[]
 for v in blank:
  if runs and v==runs[-1][-1]+1:runs[-1].append(int(v))
  else:runs.append([int(v)])
 separators=[]
 for run in runs:
  if len(run)<minimum:continue
  lo,hi=top+run[0],top+run[-1]+1;mid=(lo+hi)/2;crossing=[];support=[]
  for col in (x,y):
   above=[];below=[]
   for j,z in enumerate(blocks):
    bb=z['bbox'];over=max(0,min(col[2],bb[2])-max(col[0],bb[0]))
    if over<.5*(col[2]-col[0]):continue
    if bb[1]*h<mid<bb[3]*h:crossing.append(j)
    if z['type']=='text':
     if 0<=mid-bb[3]*h<=len(run)/2+3*scale:above.append(j)
     if 0<=bb[1]*h-mid<=len(run)/2+3*scale:below.append(j)
   support.append(dict(above=above,below=below))
  if not crossing and all(s['above'] and s['below'] for s in support):
   separators.append(dict(pixel_rect=[left,lo,right,hi],height=hi-lo,median_glyph_height=scale,minimum_height=minimum,column_support=support))
 return dict(blocked=bool(separators),separators=separators,page_size=[w,h],analysis_rect=[left,top,right,bottom],minimum_blank_height=minimum,rule='shared blank band; no existing block crosses; text above/below in both columns')
