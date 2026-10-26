import json
from pathlib import Path
from PIL import Image
import cv2,numpy as np
from table_mechanisms import grids,runs
def overlap(a,b):return max(0,min(a[3],b[3])-max(a[1],b[1]))/max(.0001,min(a[3]-a[1],b[3]-b[1]))
def bands(crop):
 a=np.asarray(crop.convert('L'))<180
 # Remove long rules before finding text baselines.
 h=cv2.morphologyEx(a.astype('uint8'),cv2.MORPH_OPEN,np.ones((1,max(20,crop.width//2)),np.uint8))
 a=a & ~h.astype(bool);density=a.sum(1);return [(s,e) for s,e in runs(density>=max(2,crop.width*.008)) if e-s>=2]

def proposals(pages,predictions):
 rows=[];tablecount=0;paircount=0
 for p in pages:
  rawpath=Path(predictions)/'raw'/(p['id']+'.json');raw=json.load(open(rawpath));bs=raw['blocks'];ts=[]
  for i,b in enumerate(bs):
   if b['type']=='table':
    tablecount+=1;g=grids(b['content'])
    if b.get('angle',0)==0 and len(g)==1 and not(g[0]['holes'] or g[0]['conflicts'] or g[0]['span_beyond_rows']):ts.append((i,b,g[0]))
  for i,l,lg in ts:
   if lg['width']!=1 or lg['rows']<2:continue
   for j,r,rg in ts:
    a,b=l['bbox'],r['bbox'];gap=b[0]-a[2]
    if j==i or rg['width']<2 or rg['rows']!=lg['rows'] or gap<0 or gap>.12 or overlap(a,b)<.6:continue
    paircount+=1;uppers=[]
    for k,u,ug in ts:
     z=u['bbox'];width=z[2]-z[0]
     if ug['width']!=1+rg['width'] or z[3]>min(a[1],b[1]) or min(a[1],b[1])-z[3]>max(.04,z[3]-z[1]):continue
     if abs(z[0]-a[0])>.15*width or abs(z[2]-b[2])>.15*width:continue
     uppers.append((k,u,ug))
    k,u,ug=max(uppers,key=lambda t:t[1]['bbox'][3]) if uppers else (None,None,None)
    idx=[i,j] if k is None else [k,i,j];boxes=[bs[t]['bbox'] for t in idx];bb=[min(t[0] for t in boxes),min(t[1] for t in boxes),max(t[2] for t in boxes),max(t[3] for t in boxes)];bridge=[];conflicts=[]
    for q,v in enumerate(bs):
     if q in idx or v['type'] in ['header','footer','page_number']:continue
     z=v['bbox'];intersection=max(0,min(bb[2],z[2])-max(bb[0],z[0]))*max(0,min(bb[3],z[3])-max(bb[1],z[1]))
     if intersection<=0:continue
     if k is not None and v['type'] in ['table_caption','title'] and z[0]>=bb[0]-.01 and z[2]<=bb[2]+.01 and z[1]>=u['bbox'][3]-.005 and z[3]<=min(a[1],b[1])+.005:bridge.append(q)
     else:conflicts.append(q)
    idx=sorted(idx+bridge);eligible=k is not None and not conflicts
    rows.append(dict(page=p['id'],image=p['image'],raw=str(rawpath),indices=idx,left=i,right=j,upper=k,bridge=bridge,bbox=bb,eligible=eligible,reason='shared_schema_graph' if eligible else ('owner_or_body_conflict' if conflicts else 'no_shared_upper_schema'),conflicts=conflicts,rows=lg['rows'],width=1+rg['width']))
 # Source bands support; no text dictionaries or GT.
 for r in rows:
  d=json.load(open(r['raw']))
  with Image.open(r['image']) as im:
   im=im.convert('RGB');w,h=im.size
   box=lambda bb:[round(v*(w if k%2==0 else h)) for k,v in enumerate(bb)]
   lbox=box(d['blocks'][r['left']]['bbox']);rbox=box(d['blocks'][r['right']]['bbox']);lb=bands(im.crop(lbox));rb=bands(im.crop(rbox));tol=max(3,np.median([e-s for s,e in rb])*.6) if rb else 3
   ly=[(s+e)/2+lbox[1] for s,e in lb];ry=[(s+e)/2+rbox[1] for s,e in rb];matches=[bool(min([abs(y-z) for z in ly],default=1e9)<=tol) for y in ry]
   r.update(source_left_bands=lb,source_right_bands=rb,source_row_alignment=matches,row_tolerance=float(tol),box=box(r['bbox']))
   if r['eligible'] and (len(rb)!=r['rows'] or not all(matches)):r.update(eligible=False,reason='source_baseline_ambiguous')
 return rows,tablecount,paircount
