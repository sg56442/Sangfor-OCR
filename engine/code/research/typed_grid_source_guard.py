"""Reject text panels with outgoing interior graph stems; no IDs/annotations/word lists."""
import copy,cv2,numpy as np
from native_typed_grid import apply as old_apply
from missing_table_geometry import proposals
from html import escape

def guard(image,blocks,proposal):
 w,h=image.size;bb=proposal['bbox'];near=[b for b in blocks if b['type']=='image' and b['bbox'][1]>=bb[3] and b['bbox'][1]-bb[3]<.12 and min(b['bbox'][2],bb[2])>max(b['bbox'][0],bb[0])]
 if not near:return True,dict(reason='no_downstream_graph_region',stems=[])
 end=min(1,max(b['bbox'][3] for b in near));y0=round(bb[3]*h);y1=round(end*h);x0=round(bb[0]*w);x1=round(bb[2]*w)
 a=np.asarray(image.crop((x0,y0,x1,y1)).convert('L'));ink=(a<180).astype('uint8');length=max(8,round(.015*h));lines=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((length,1),np.uint8));num,labels,stats,cents=cv2.connectedComponentsWithStats(lines,8)
 bodies=sorted([blocks[i] for i in proposal['indices']],key=lambda b:b['bbox'][1])[proposal['columns']:];stems=[]
 for sx,sy,sw,sh,area in stats[1:]:
  px=x0+sx+sw/2
  if sh<length or sy>.025*h:continue
  for j,b in enumerate(bodies):
   l,r=b['bbox'][0]*w,b['bbox'][2]*w
   if l+.2*(r-l)<px<r-.2*(r-l):stems.append(dict(body=j,source_rect=[int(x0+sx),int(y0+sy),int(sw),int(sh)]));break
 reject=len({s['body'] for s in stems})>=2
 return not reject,dict(reason='outgoing_interior_graph_connectors' if reject else 'no_multi_panel_graph_connectors',stems=stems,nearby_image_bboxes=[b['bbox'] for b in near])

def apply(image,blocks):
 result=copy.deepcopy(blocks);replace={};remove=set();ds=[]
 for p in sorted(proposals(blocks),key=lambda p:(-p['columns'],p['column_center_error'])):
  items=sorted([blocks[i] for i in p['indices']],key=lambda b:b['bbox'][1]);n=p['columns'];rows=[sorted(items[:n],key=lambda b:b['bbox'][0]),sorted(items[n:],key=lambda b:b['bbox'][0])];typed=all(b['type']=='title' for b in rows[0]) and all(b['type']=='text' for b in rows[1]);ok,evidence=guard(image,blocks,p);accept=typed and ok and not remove.intersection(p['indices']);ds.append(dict(indices=p['indices'],bbox=p['bbox'],typed_row_support=typed,source_guard=ok,selected=accept,**evidence))
  if not accept:continue
  markup='<table>'+''.join('<tr>'+''.join('<td>'+escape(b.get('content',''))+'</td>' for b in row)+'</tr>' for row in rows)+'</table>';b=dict(blocks[min(p['indices'])]);b.update(type='table',bbox=p['bbox'],content=markup,angle=0);b.pop('merge_prev',None);replace[min(p['indices'])]=b;remove.update(p['indices'])
 return [replace[i] if i in replace else b for i,b in enumerate(result) if i not in remove or i in replace],ds,bool(replace)
