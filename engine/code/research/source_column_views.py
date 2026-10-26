"""Original-pixel sustained vertical boundaries define column identity, not native HTML."""
import cv2,numpy as np
from table_mechanisms import runs

def columns(image):
 a=np.asarray(image.convert('L'));h,w=a.shape;ink=(a<160).astype('uint8')
 # Dilate only for line detection to tolerate slight skew; crops remain unchanged.
 v=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((max(10,h//8),1),np.uint8));v=cv2.dilate(v,np.ones((1,5),np.uint8))
 xs=[int((s+e)//2) for s,e in runs(v.mean(0)>.35)];inner=[x for x in xs if .04*w<x<.96*w]
 if not 1<=len(inner)<=10:return [],dict(reason='no_sustained_internal_column_boundaries',xs=xs)
 bounds=[0]+inner+[w]
 if min(np.diff(bounds))<max(12,w*.035):return [],dict(reason='narrow_or_spurious_column',xs=xs)
 return list(zip(bounds,bounds[1:])),dict(reason='sustained_original_vertical_rulings',xs=xs,bounds=bounds)

def row_boundaries(image):
 a=np.asarray(image.convert('L'));h,w=a.shape;ink=(a<160).astype('uint8');lines=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(8,round(w*.55))),np.uint8));ys=[int((s+e)//2) for s,e in runs(lines.mean(1)>.55)]
 merged=[]
 for y in ys:
  if not .015*h<y<.985*h:continue
  if merged and y-merged[-1]<=max(3,h*.006):merged[-1]=round((merged[-1]+y)/2)
  else:merged.append(y)
 return [0]+merged+[h]

def assemble_columns(images,answers,x_intervals):
 """Per-column image ruling intervals identify source cells; union yanchors yieldsrowspan.
 Requires only local decode vs image band correspondence; no native/GT rowcounts.
 """
 from table_mechanisms import grids
 from lxml import html,etree
 import copy
 ys=[row_boundaries(im) for im in images];parsed=[];reasons=[]
 for j,(s,bounds) in enumerate(zip(answers,ys)):
  gs=grids(s)
  if len(gs)!=1 or gs[0]['conflicts'] or gs[0]['holes'] or gs[0]['span_beyond_rows']:return None,dict(reason='invalid_column_decode',column=j,source_y_intervals=ys)
  g=gs[0]
  if g['rows']!=len(bounds)-1:return None,dict(reason='local_rows_image_bands_disagree',column=j,returned_rows=g['rows'],image_bands=len(bounds)-1,source_y_intervals=ys)
  root=html.fromstring('<div>'+s+'</div>');trs=root.xpath('.//table')[0].xpath('.//tr');cells=[]
  for r,row in enumerate(trs):
   cs=[c for c in g['cells'] if c['row']==r];nodes=row.xpath('./td|./th')
   if not cs:continue
   spans={c['rowspan'] for c in cs}
   if len(spans)!=1 or sum(c['colspan'] for c in cs)!=g['width']:return None,dict(reason='ambiguous_within_column_span',column=j,source_y_intervals=ys)
   rs=next(iter(spans));new=html.Element('td')
   # Source column bounds justify combining horizontal subcells, retaining all markup.
   for ni,node in enumerate(nodes):
    if ni:
     if len(new):new[-1].tail=(new[-1].tail or '')+' '
     else:new.text=(new.text or '')+' '
    if node.text:
     if len(new):new[-1].tail=(new[-1].tail or '')+node.text
     else:new.text=(new.text or '')+node.text
    for child in node:new.append(copy.deepcopy(child))
   cells.append((bounds[r],bounds[r+rs],new))
  parsed.append(cells)
 # Cluster measured line thickness/skew within a fixed image-relative tolerance.
 tol=max(3,images[0].height*.006);all_y=sorted(set(y for bounds in ys for y in bounds));groups=[]
 for y in all_y:
  if groups and y-groups[-1][0]<=tol:groups[-1].append(y)
  else:groups.append([y])
 lookup={y:i for i,group in enumerate(groups) for y in group};table=html.Element('table');trs=[etree.SubElement(table,'tr') for _ in range(len(groups)-1)];mapped=[]
 for col,cells in enumerate(parsed):
  for y0,y1,node in cells:
   r0,r1=lookup[y0],lookup[y1]
   if r1<=r0:return None,dict(reason='collapsed_source_interval')
   if r1-r0>1:node.set('rowspan',str(r1-r0))
   trs[r0].append(node);mapped.append(dict(column=col,x_interval=x_intervals[col],source_y_interval=[y0,y1],assembled_rows=[r0,r1]))
 rendered=html.tostring(table,encoding='unicode');g=grids(rendered)
 if not g or g[0]['holes'] or g[0]['conflicts']:return None,dict(reason='union_grid_coverage_failure',mapped=mapped)
 return rendered,dict(reason='source_column_ruling_interval_union',mapped=mapped,source_y_intervals=ys)
