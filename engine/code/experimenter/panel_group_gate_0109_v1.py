"""Complete enclosed single-column glyph group, one or several actual native text leaves."""
import cv2,numpy as np,math
from finite_request_identity_0101_v1 import helper

def admit(record,candidate,view):
 if record.get('status')!='CONSUMED' or not record.get('finished_normally'):return False,dict(reason='layout_failed_or_truncated')
 leaves=helper().parse_layout_output(record['raw_answer'])
 if not leaves or any(b.type!='text' or b.angle not in [0,None] for b in leaves):return False,dict(reason='nontext_or_rotated_relation')
 if max(b.bbox[0] for b in leaves)>=min(b.bbox[2] for b in leaves):return False,dict(reason='not_shared_single_column')
 for i,a in enumerate(leaves):
  for b in leaves[i+1:]:
   if min(a.bbox[2],b.bbox[2])>max(a.bbox[0],b.bbox[0]) and min(a.bbox[3],b.bbox[3])>max(a.bbox[1],b.bbox[1]):return False,dict(reason='overlapping_or_duplicate_leaves')
 gray=np.asarray(view.convert('L'));h,w=gray.shape;n,labels,stats,_=cv2.connectedComponentsWithStats((gray>=210).astype('uint8'),8);index=1+np.argmax(stats[1:,4]);mask=(labels==index).astype('uint8');contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);interior=np.zeros_like(mask);cv2.drawContours(interior,contours,-1,1,cv2.FILLED)
 ink=((gray<185)&(interior>0)).astype('uint8');n,ll,ss,_=cv2.connectedComponentsWithStats(ink,8);glyphs=[list(map(int,q)) for q in ss[1:] if q[4]>=3]
 boxes=[[math.floor(b.bbox[0]*w),math.floor(b.bbox[1]*h),math.ceil(b.bbox[2]*w),math.ceil(b.bbox[3]*h)] for b in leaves]
 outside=[q for q in glyphs if not any(bb[0]<=q[0] and bb[1]<=q[1] and q[0]+q[2]<=bb[2] and q[1]+q[3]<=bb[3] for bb in boxes)]
 return not outside,dict(reason='complete_single_column_enclosed_text_group' if not outside else 'actual_glyph_not_covered',glyph_count=len(glyphs),outside=outside,boxes=boxes,leaf_count=len(leaves),recognition_view='entire_original_closed_panel',relation='original_image_and_childbox_preserved')
