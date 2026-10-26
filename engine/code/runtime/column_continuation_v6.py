"""Directed terminal rollover after displays inside one source parent region.
Keeps frozen v5b; no strings/identities/GT as region features; only merge_prev.
"""
import numpy as np
from column_continuation_v5b import apply as previous
from reading_region_band_v2 import inspect as shared_band

def directed(image,blocks,a,b,flow):
 x,y=blocks[a]['bbox'],blocks[b]['bbox'];w,h=image.size
 rec=dict(allowed=False,reason='non_display_obstacle')
 obs=flow.get('protected_objects',[])
 if not obs or flow.get('horizontal_rules_pixels') or any(z['type']!='equation' for z in obs):return rec
 if any(z['bbox'][3]>x[1]+.002 for z in obs):return dict(rec,reason='display_not_before_terminal')
 ev=shared_band(image,blocks,a,b);rec['shared_band']=ev
 if ev['blocked']:return dict(rec,reason='separate_reading_regions')
 # Full-width native objects delimit parent bands, including tables below body.
 top,bottom=0.,1.;boundaries=[]
 for j,z in enumerate(blocks):
  if z['type'] not in ('title','image','table'):continue
  bb=z['bbox']
  if bb[0]<=x[0]+.01 and bb[2]>=y[2]-.01:
   if bb[3]<=min(x[1],y[1]):top=max(top,bb[3]);boundaries.append(j)
   elif bb[1]>=max(x[3],y[3]):bottom=min(bottom,bb[1]);boundaries.append(j)
   else:return dict(rec,reason='transverse_parent_boundary',obstacle=j)
 def overlap(bb,col):return max(0,min(bb[2],col[2])-max(bb[0],col[0]))/(col[2]-col[0])
 members=[(j,z) for j,z in enumerate(blocks) if z['type'] not in ('header','footer','page_number') and z['bbox'][1]>=top and z['bbox'][3]<=bottom and (overlap(z['bbox'],x)>=.5 or overlap(z['bbox'],y)>=.5)]
 left=[(j,z) for j,z in members if overlap(z['bbox'],x)>=.5];right=[(j,z) for j,z in members if overlap(z['bbox'],y)>=.5]
 if any(j!=a and z['bbox'][3]>x[3]+.002 for j,z in left):return dict(rec,reason='left_not_terminal')
 if any(j!=b and z['bbox'][1]<y[1]-.002 for j,z in right):return dict(rec,reason='right_not_initial')
 if len(left)<2 or len(right)<2:return dict(rec,reason='insufficient_parent_support')
 # Gutter must separate the full two-column parent, not merely the two ROIs.
 py0=min(z['bbox'][1] for j,z in members);py1=max(z['bbox'][3] for j,z in members)
 gap=y[0]-x[2]
 if gap<=0:return dict(rec,reason='no_positive_gutter')
 rect=[round((x[2]+.2*gap)*w),round(py0*h),round((y[0]-.2*gap)*w),round(py1*h)]
 if rect[2]-rect[0]<3:return dict(rec,reason='gutter_too_narrow')
 pix=np.asarray(image.crop(rect).convert('L'));ink=pix<min(210,float(np.percentile(pix,90))-35);density=float(ink.mean())
 rec.update(parent_band=[top,bottom],parent_boundaries=boundaries,left_members=[j for j,z in left],right_members=[j for j,z in right],gutter_rect=rect,gutter_ink_fraction=density,earlier_display_indices=[z['index'] for z in obs])
 if density>.01:return dict(rec,reason='gutter_not_continuous')
 return dict(rec,allowed=True,reason='same_parent_terminal_to_initial_after_display')

def apply(image,blocks):
 out,records=previous(image,blocks)
 for r in records:
  if r['reason']!='interrupted_source_reading_flow':continue
  a,b=r['indices'];ev=directed(image,blocks,a,b,r['flow_evidence']);r['directed_evidence']=ev
  if ev['allowed']:out[b]['merge_prev']=True;r.update(accepted=True,reason='directed_terminal_after_display')
 return out,records
