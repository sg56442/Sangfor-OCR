"""Conservative reading-flow admission for column continuation.
Frozen v2 entry/line geometry; only merge_prev changes. No lexicon/identity/GT.
"""
import cv2,numpy as np
from column_continuation_v2 import apply as v2_apply

def flow_evidence(image,blocks,a,b):
 left,right=blocks[a]['bbox'],blocks[b]['bbox'];width=left[2]-left[0]
 # To roll from the left-column bottom to the right-column top, the left
 # stream must not cross a non-prose region between those vertical positions.
 top,bottom=right[1],left[1];obstacles=[]
 for j,c in enumerate(blocks):
  if j in (a,b) or c['type'] not in ('image','table','title','equation'):continue
  z=c['bbox'];over=max(0,min(z[2],left[2])-max(z[0],left[0]))
  if c['type'] in ('image','table') and z[0]<=left[0]+.01 and z[2]>=right[2]-.01 and 0<=right[1]-z[3]<=.04:
   obstacles.append(dict(index=j,type=c['type'],bbox=z,reason='shared_transverse_object_before_right_start',crosses_both_columns=True))
  if over>=.3*width and z[3]>top and z[1]<bottom and z[3]<=left[1]+.002:
   obstacles.append(dict(index=j,type=c['type'],bbox=z,left_overlap=over/width,crosses_both_columns=z[0]<left[2] and z[2]>right[0]))
 # Detect visible horizontal rules, including rules absent from native layout.
 w,h=image.size;x0,x1=round(left[0]*w),round(left[2]*w);y0,y1=round(top*h),round(bottom*h)
 rules=[]
 if x1>x0 and y1>y0:
  g=np.asarray(image.crop((x0,y0,x1,y1)).convert('L'));mask=(g<min(210,float(np.percentile(g,90))-30)).astype('uint8')
  length=max(12,round(.65*(x1-x0)));opened=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((1,length),np.uint8))
  n,lab,stats,centers=cv2.connectedComponentsWithStats(opened,8)
  for x,y,ww,hh,area in stats[1:]:
   if ww>=length and hh<=max(5,.015*h):rules.append([int(x+x0),int(y+y0),int(x+ww+x0),int(y+hh+y0)])
 return dict(corridor=[left[0],top,left[2],bottom],protected_objects=obstacles,horizontal_rules_pixels=rules,blocked=bool(obstacles or rules))

def apply(image,blocks):
 out,records=v2_apply(image,blocks)
 for r in records:
  if not r['accepted']:continue
  a,b=r['indices'];ev=flow_evidence(image,blocks,a,b);r['flow_evidence']=ev
  if ev['blocked']:
   if 'merge_prev' in blocks[b]:out[b]['merge_prev']=blocks[b]['merge_prev']
   else:out[b].pop('merge_prev',None)
   r.update(accepted=False,reason='interrupted_source_reading_flow')
 return out,records
