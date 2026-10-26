"""Conservative source-gutter column edge; no text semantics, identities or GT."""
import numpy as np
from prose_geometry_0143_v1 import intersection

def anchor(q,native,image):
 proof=dict(accepted=False,reason='replacement_keeps_ownership')
 if q['replace_owners']:return q,proof
 b=q['source_bbox'];old=q['insert_before'];right=[i for i,v in enumerate(native) if v['type']=='text' and v.get('content') and v['bbox'][0]>=b[2]+.001 and min(v['bbox'][3],b[3])>max(v['bbox'][1],b[1])]
 if not right:return q,dict(accepted=False,reason='no_adjacent_column')
 x=min(native[i]['bbox'][0] for i in right);width=b[2]-b[0]
 if x-b[2]>.15*width:return q,dict(accepted=False,reason='nonadjacent_column')
 # A common title crossing the gutter bounds the article; no sentence/label interpretation.
 titles=[v['bbox'] for v in native if v['type']=='title' and v['bbox'][0]<b[2] and v['bbox'][2]>x and v['bbox'][3]<=b[1]]
 if not titles:return q,dict(accepted=False,reason='no_common_article_boundary')
 top=max(t[3] for t in titles);below=[v['bbox'][1] for v in native if v['type']=='title' and v['bbox'][0]<b[2] and v['bbox'][2]>x and v['bbox'][1]>=b[3]];bottom=min(below) if below else b[3]
 band=[b[2],top,x,bottom]
 blockers=[i for i,v in enumerate(native) if v['type'] in ['table','image','image_block','title'] and intersection(band,v['bbox'])>0]
 if blockers:return q,dict(accepted=False,reason='mixed_or_spanning_owner',blockers=blockers)
 rows=[i for i,v in enumerate(native) if v['type']=='text' and v.get('content') and abs(v['bbox'][0]-x)<=.003 and v['bbox'][1]>=top-.003 and v['bbox'][1]<bottom and v['bbox'][3]<=bottom+.003]
 if len(rows)<2:return q,dict(accepted=False,reason='insufficient_column_support')
 # All column paragraphs must share their right boundary and monotonic native ownership.
 if max(native[i]['bbox'][2] for i in rows)-min(native[i]['bbox'][2] for i in rows)>.006:return q,dict(accepted=False,reason='variable_column_width')
 ordered=sorted(rows,key=lambda i:native[i]['bbox'][1])
 if ordered!=sorted(rows):return q,dict(accepted=False,reason='nonmonotonic_native_column')
 w,h=image.size;lo=int(np.ceil(b[2]*w))+1;hi=int(np.floor(x*w))-1;y=int(np.ceil(top*h))+1;Y=int(np.floor(bottom*h))-1
 if hi-lo<2 or Y-y<10:return q,dict(accepted=False,reason='no_resolved_gutter')
 gray=np.asarray(image.convert('L'))[y:Y,lo:hi];tests=[]
 for threshold in [160,200]:
  ink=(gray<threshold);tests.append(dict(threshold=threshold,ink_fraction=float(ink.mean()),clear_columns=int((ink.mean(axis=0)<=.01).sum())))
 if any(v['clear_columns']<2 or v['ink_fraction']>.08 for v in tests):return q,dict(accepted=False,reason='gutter_not_clear',tests=tests)
 target=ordered[0]
 return dict(q,insert_before=target),dict(accepted=target!=old,reason='source_gutter_column_edge' if target!=old else 'already_column_start',old_anchor=old,new_anchor=target,column_owners=ordered,band=band,gutter_pixels=[lo,y,hi,Y],tests=tests,edges=[dict(before='new_complete_group',after=i) for i in ordered])
