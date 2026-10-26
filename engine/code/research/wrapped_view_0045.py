"""Anchor-ending complete-record spacing; no OCR/GT, all original pixels retained."""
import cv2,numpy as np,re
from spacing_gate_0042 import grid
from table_mechanisms import runs
from PIL import Image
def transform(im,content):
 g=grid(content)
 if not g or not 3<=g['width']<=12:return None,dict(reason='unsupported_grid')
 a=np.array(im);h,w=a.shape[:2];m=(np.array(im.convert('L'))<180).astype('uint8');hr=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((1,max(30,w//4)),np.uint8));vr=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((max(30,h//3),1),np.uint8));ink=m&~(hr|vr)
 nn,ll,ss,_=cv2.connectedComponentsWithStats(ink,8);keep=np.zeros(nn,dtype='uint8');keep[1:]=(ss[1:,cv2.CC_STAT_AREA]>=6)&(ss[1:,cv2.CC_STAT_HEIGHT]>=3)&(ss[1:,cv2.CC_STAT_WIDTH]>=2);ink=keep[ll]
 gutters=[(s,e) for s,e in runs(ink[int(h*.2):].sum(0)==0) if e-s>=max(6,w*.012) and s>0 and e<w]
 if len(gutters)!=g['width']-1:return None,dict(reason='ambiguous_columns',gutters=gutters,width=g['width'])
 xs=[0]+[(s+e)//2 for s,e in gutters]+[w]
 counts=[sum(bool(re.search(r'\d',c['text'])) and c['rowspan']==1 and c['colspan']==1 for c in g['cells'] if c['col']==col) for col in range(1,g['width'])];col=1+int(np.argmax(counts))
 if max(counts)<3:return None,dict(reason='insufficient_numeric_anchors')
 bands=[(s,e) for s,e in runs(ink[:,xs[col]:xs[col+1]].sum(1)>0) if s>h*.2 and e-s>=3];med=float(np.median([e-s for s,e in bands])) if bands else 0;bands=[(s,e) for s,e in bands if e-s>=max(3,med*.5)];stub=[(s,e) for s,e in runs(ink[:,:xs[1]].sum(1)>0) if e-s>=3];blank=runs(ink.sum(1)==0);seams=[];bindings=[]
 for s,e in bands:
  aligned=[(u,v) for u,v in stub if abs((u+v-s-e)/2)<=max(3,med*.4)]
  if len(aligned)!=1:continue
  gaps=[(u,v) for u,v in blank if u>=e and u<=e+med*.7 and v-u>=3 and v<h-3]
  if not gaps:continue
  u,v=gaps[0];seams.append((u+v)//2);bindings.append(dict(anchor_band=[s,e],left_band=aligned[0],gap=[u,v]))
 seams=sorted(y for y in set(seams) if (m&~(hr|vr))[y-1:y+1].sum()==0)
 if len(seams)<2:return None,dict(reason='insufficient_complete_record_seams',gutters=gutters,anchor_column=col,bindings=bindings)
 pad=max(8,min(64,int(np.ceil(med*2))));chunks=[];mapping=[];start=0;offset=0
 for y in seams+[h]:
  chunks.append(a[start:y]);mapping.append([start,y,offset,offset+y-start]);offset+=y-start
  if y<h:chunks.append(np.full((pad,w,3),255,np.uint8));offset+=pad
  start=y
 result=np.concatenate(chunks);assert np.array_equal(np.concatenate([result[z0:z1] for _,_,z0,z1 in mapping]),a)
 return Image.fromarray(result),dict(reason='complete_anchor_ending_record_spacing',gutters=gutters,anchor_column=col,bindings=bindings,seams=seams,pad=pad,median_height=med,mapping=mapping,reversible_pixel_exact=True,original_size=im.size,view_size=[result.shape[1],result.shape[0]])
