"""Input/source-only independent list columns; preserve all existing cell strings."""
import re,cv2,numpy as np
from spacing_gate_0042 import grid
from bs4 import BeautifulSoup
cv2.setNumThreads(2)
def candidate(im,b):
 if b.get('angle',0):return None,'rotation'
 g=grid(b.get('content') or '')
 if not g or g['width']<4 or g['width']>8 or g['width']%2 or g['rows']<12:return None,'not_multiple_long_pairs'
 if any(c['col']//2!=(c['col']+c['colspan']-1)//2 for c in g['cells']):return None,'cross_pair_title_or_cells'
 for c in g['cells']:
  if c['rowspan']>1 and not any(v['row']==c['row'] and v['col']==(c['col']^1) and v['rowspan']==c['rowspan'] for v in g['cells']):return None,'unequal_pair_rowspan'
 cells={(c['row'],c['col']):c['text'] for c in g['cells']};pairs=g['width']//2;headers=[];lines=[]
 for p in range(pairs):
  h=[];ls=[];records=0;ok=0
  for r in range(g['rows']):
   x=cells.get((r,2*p),'');y=cells.get((r,2*p+1),'')
   if x.strip() and not y.strip():h.append(r)
   if x.strip() and y.strip():
    records+=1;ok+=1<=len(x.strip())<=8 and len(y.strip())>=8 and not re.search(r'\d',x+y)
   if x or y:ls.append('  '.join(z for z in [x,y] if z))
  if len(h)<2 or records<8 or ok/records<.8:return None,'not_independent_prose_sections'
  headers.append(h);lines.append(ls)
 if any(set(a)==set(b) for i,a in enumerate(headers) for b in headers[i+1:]):return None,'shared_row_headings'
 w,h=im.size;box=[round(v*s) for v,s in zip(b['bbox'],[w,h,w,h])];a=np.array(im.convert('L'))[box[1]:box[3],box[0]:box[2]];ink=(a<180).astype('uint8');hh,ww=ink.shape
 # Ruled tables/forms and cross-column titles must not be turned into independent prose.
 horiz=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(12,int(.7*ww))),np.uint8))
 vert=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((max(12,int(.4*hh)),1),np.uint8))
 if horiz.any() or vert.any():return None,'ruling_or_separator'
 seams=[]
 for p in range(1,pairs):
  center=ww*p/pairs;lo=max(0,int(center-.12*ww/pairs));hi=min(ww,int(center+.12*ww/pairs));good=ink[:,lo:hi].mean(axis=0)<=.002;best=[];run=[]
  for j,x in enumerate(good):
   if x:run.append(j+lo)
   else:
    if len(run)>len(best):best=run
    run=[]
  if len(run)>len(best):best=run
  if len(best)<4:return None,'no_fullheight_gutter'
  seams.append([best[0],best[-1]+1])
 text='\n\n'.join('\n'.join(ls) for ls in lines)
 # The native cell strings are emitted exactly once, only whitespace/structure changes.
 assert sum(len(v) for v in cells.values())==sum(len(c['text']) for c in g['cells'])
 return dict(text=text,headers=headers,seams=seams,pairs=pairs,rows=g['rows'],box=box),'independent_staggered_sections_and_source_gutters'
