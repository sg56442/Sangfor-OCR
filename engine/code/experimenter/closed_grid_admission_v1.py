"""Narrow supported pre-call scope; explicit refusals before model usage."""
import numpy as np,cv2

def admit(image,proposal):
 if not proposal.get('eligible'):return dict(admitted=False,reason=proposal['reason'])
 if proposal['native_type'] not in ('text','title'):return dict(admitted=False,reason='outside_text_task_mismatch_scope')
 if proposal['outside_ink_components']:return dict(admitted=False,reason='same_owner_outside_grid_content')
 if len(proposal['cells'])<2:return dict(admitted=False,reason='single_box_not_grid')
 # Reject content touching physical cell boundaries, which includes many plotted curves/arrows.
 im=np.asarray(image.convert('L'));cross=[]
 for i,c in enumerate(proposal['cells']):
  x0,y0,x1,y1=c['pixel_box'];a=(im[y0:y1+1,x0:x1+1]<185).astype('uint8')
  h,w=a.shape
  if h<12 or w<12:return dict(admitted=False,reason='cell_too_small')
  H=cv2.morphologyEx(a,cv2.MORPH_OPEN,np.ones((1,max(8,w//2)),np.uint8));V=cv2.morphologyEx(a,cv2.MORPH_OPEN,np.ones((max(8,h//2),1),np.uint8))
  content=a & (1-cv2.dilate(H|V,np.ones((3,3),np.uint8)))
  inner=content[3:-3,3:-3]
  edge=int(inner[:2].sum()+inner[-2:].sum()+inner[:,:2].sum()+inner[:,-2:].sum())
  if edge>4:cross.append(dict(cell=i,near_boundary_ink=edge))
 if cross:return dict(admitted=False,reason='content_near_cell_boundary_or_crossing',cells=cross)
 return dict(admitted=True,reason='text_owner_closed_partition_no_outside_no_boundary_contact',limits='Not a character-level guarantee; source and normal support required.')
