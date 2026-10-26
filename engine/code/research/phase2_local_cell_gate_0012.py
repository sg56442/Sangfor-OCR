"""Source-only local physical-cell boundaries; HTML supplies topology, never coordinates."""
import cv2,numpy as np
from table_mechanisms import grids
from source_cell_occupancy_v1 import cell_occupancy
from table_partition_constraint_v1 import bands

def detect(image,raw,index,threshold=185):
 b=raw['blocks'][index];w,h=image.size
 if b['type']!='table' or b.get('angle',0)!=0:return dict(reason='type_or_angle',cells=[])
 box=[max(0,round(v*(w if j%2==0 else h))) for j,v in enumerate(b['bbox'])];box[2]=min(w,box[2]);box[3]=min(h,box[3]);x0,y0,x1,y1=box
 if min(x1-x0,y1-y0)<25:return dict(reason='small_owner',cells=[])
 try:gg=grids(b['content'])
 except Exception:return dict(reason='parse_failure',cells=[])
 if len(gg)!=1 or any(gg[0][k] for k in ['conflicts','holes','span_beyond_rows']):return dict(reason='html_invalid',cells=[])
 g=gg[0];search=[max(0,x0-3),max(0,y0-3),min(w,x1+3),min(h,y1+3)];ink=(np.asarray(image.convert('L').crop(search))<threshold).astype('uint8');rh,rw=ink.shape
 H=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(18,rw//8)),np.uint8));V=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((max(16,rh//8),1),np.uint8))
 xs=[(s+e-1)//2 for s,e in bands(V.sum(0)>=max(20,rh*.25))];ys=[(s+e-1)//2 for s,e in bands(H.sum(1)>=max(35,rw*.30))]
 result=dict(reason='axis_count_mismatch',cells=[],xs=xs,ys=ys,search=search,owner=box,html_shape=[g['rows'],g['width']],source_shape=[len(ys)-1,len(xs)-1])
 if len(xs)!=g['width']+1 or len(ys)!=g['rows']+1:return result
 # First/last observed axes must delimit the current native table, not an arbitrary interior subgrid.
 if max(abs(xs[0]+search[0]-x0),abs(xs[-1]+search[0]-x1),abs(ys[0]+search[1]-y0),abs(ys[-1]+search[1]-y1))>8:return dict(result,reason='axes_do_not_cover_native_owner')
 def he(y,l,r):return float(H[max(0,y-2):y+3,l:r+1].max(0).mean())
 def ve(x,t,b):return float(V[t:b+1,max(0,x-2):x+3].max(1).mean())
 cells=[]
 for i,c in enumerate(g['cells']):
  r,c0,rs,cs=(c[k] for k in ['row','col','rowspan','colspan']);r1,c1=r+rs,c0+cs;xx0,xx1,yy0,yy1=xs[c0],xs[c1],ys[r],ys[r1];edges=[he(yy0,xx0,xx1),he(yy1,xx0,xx1),ve(xx0,yy0,yy1),ve(xx1,yy0,yy1)];internal=[he(ys[z],xx0,xx1) for z in range(r+1,r1)]+[ve(xs[z],yy0,yy1) for z in range(c0+1,c1)];pix=[xx0+search[0],yy0+search[1],xx1+search[0],yy1+search[1]]
  junction=all(H[max(0,y-2):y+3,max(0,x-2):x+3].any() and V[max(0,y-2):y+3,max(0,x-2):x+3].any() for x in [xx0,xx1] for y in [yy0,yy1]);reason='local_closed';safe=True
  if min(edges)<.96 or not junction:safe=False;reason='local_boundary_open'
  elif internal and max(internal)>.10:safe=False;reason='native_span_crosses_physical_partition'
  elif min(xx1-xx0,yy1-yy0)<12:safe=False;reason='narrow_cell'
  foreign=[]
  for j,o in enumerate(raw['blocks']):
   if j==index:continue
   q=[round(v*(w if k%2==0 else h)) for k,v in enumerate(o['bbox'])]
   if min(pix[2],q[2])-max(pix[0],q[0])>2 and min(pix[3],q[3])-max(pix[1],q[1])>2:foreign.append(j)
  if foreign:safe=False;reason='foreign_owner'
  occ=cell_occupancy(image,pix) if safe else None
  if occ and not occ['eligible']:safe=False;reason=occ['reason']
  cells.append(dict(cell_index=i,row=r,col=c0,rowspan=rs,colspan=cs,pixel_box=pix,content=c['text'],safe=safe,reason=reason,edges=edges,internal_edges=internal,junction=junction,foreign=foreign,occupancy=occ))
 # Two-axis independently closed adjacent cells anchor local row/column correspondence.
 for a in cells:
  row_neighbors=[b['cell_index'] for b in cells if b is not a and b['safe'] and b['row']==a['row'] and b['rowspan']==a['rowspan'] and (b['col']+b['colspan']==a['col'] or a['col']+a['colspan']==b['col'])]
  col_neighbors=[b['cell_index'] for b in cells if b is not a and b['safe'] and b['col']==a['col'] and b['colspan']==a['colspan'] and (b['row']+b['rowspan']==a['row'] or a['row']+a['rowspan']==b['row'])]
  a.update(row_anchors=row_neighbors,column_anchors=col_neighbors,eligible=a['safe'] and bool(row_neighbors) and bool(col_neighbors))
 return dict(result,reason='local_axes_mapped',cells=cells)
