"""Shared top-row ownership diagnostic, source/native/response only."""
import numpy as np,cv2,re
from bs4 import BeautifulSoup
from spacing_gate_0042 import grid

def norm(s):return ' '.join(s.split())
def geometry(im,table,caption,expanded):
 a=np.asarray(im.convert('L'));h,w=a.shape;tb=[round(v*s) for v,s in zip(table['bbox'],[w,h,w,h])];cb=[round(v*s) for v,s in zip(caption['bbox'],[w,h,w,h])];eb=expanded['expanded_box'];reason={'accepted':False}
 if table.get('angle',0) or caption.get('angle',0):return dict(reason,reason='rotation')
 if not (eb[1]<tb[1] and cb[1]<tb[1] and cb[3]<=tb[1]+(cb[3]-cb[1])/2 and cb[0]>=tb[0]-3 and cb[2]<=tb[2]+3):return dict(reason,reason='not_adjacent_top_caption')
 region=a[max(0,eb[1]):min(h,tb[1]+max(1,cb[3]-cb[1])),tb[0]:tb[2]];n,l,stats,c=cv2.connectedComponentsWithStats((region<180).astype('uint8'),8);cs=[]
 for x,y,cw,ch,area in stats[1:]:
  if area>=6 and cw>=2 and ch>=3 and cw<=200 and ch<=150:
   cs.append([int(x+tb[0]),int(y+max(0,eb[1])),int(x+cw+tb[0]),int(y+ch+max(0,eb[1]))])
 cap=[b for b in cs if cb[0]<=(b[0]+b[2])/2<=cb[2] and cb[1]<=(b[1]+b[3])/2<=cb[3]]
 other=[b for b in cs if (b[0]+b[2])/2>cb[2] and (b[1]+b[3])/2<tb[1]]
 if len(cap)<3 or len(other)<3:return dict(reason,reason='insufficient_distinct_glyph_groups')
 bounds=lambda z:[min(b[0] for b in z),min(b[1] for b in z),max(b[2] for b in z),max(b[3] for b in z)]
 cbox=bounds(cap);obox=bounds(other);ch=float(np.median([b[3]-b[1] for b in cap]));oh=float(np.median([b[3]-b[1] for b in other]));over=max(0,min(cbox[3],obox[3])-max(cbox[1],obox[1]));gap=abs(float(np.median([b[3] for b in cap]))-float(np.median([b[3] for b in other])))
 def bands(box):
  ys=np.flatnonzero((a[box[1]:box[3],box[0]:box[2]]<180).any(axis=1));return 0 if len(ys)==0 else 1+int(np.sum(np.diff(ys)>3))
 cbands,obands=bands(cbox),bands(obox)
 ok=cbox[2]<obox[0] and over>=.2*min(ch,oh) and gap<=max(ch,oh) and cbands==obands==1
 return dict(accepted=bool(ok),reason='shared_single_glyph_band' if ok else 'baseline_or_multiline_conflict',caption_glyph_box=cbox,new_glyph_box=obox,caption_components=len(cap),new_components=len(other),pixel_line_bands=[cbands,obands],median_heights=[ch,oh],baseline_gap=gap,vertical_overlap=over,table_box=tb,caption_box=cb,expanded_box=eb)

def select(im,old,new,blocks,owner,expanded):
 def no(reason,**kw):return dict(accepted=False,reason=reason,**kw)
 a=grid(old);b=grid(new)
 if not a or not b or a['width']!=b['width'] or b['rows']!=a['rows']+1:return no('not_single_new_top_row')
 top=[c for c in b['cells'] if c['row']==0 and norm(c['text'])]
 if len(top)<2 or any(c['rowspan']!=1 for c in top):return no('not_multiple_top_cells')
 ordered=lambda g,skip:[norm(c['text']) for c in sorted(g['cells'],key=lambda c:(c['row'],c['col'])) if c['row']>=skip and norm(c['text'])]
 if ordered(a,0)!=ordered(b,1):return no('original_nonempty_cell_stream_changed')
 pairs=[]
 for j,z in enumerate(blocks):
  if z['type']!='table_caption' or not isinstance(z.get('content'),str):continue
  for c in top:
   if norm(z['content'])==norm(c['text']):pairs.append((j,c))
 if len(pairs)!=1:return no('caption_content_not_unique')
 j,c=pairs[0];caption=blocks[j];text=norm(caption['content'])
 # Any independent exact native occurrence makes attribution nonunique.
 if sum(isinstance(z.get('content'),str) and norm(z['content'])==text for z in blocks)!=1:return no('caption_owner_not_unique')
 if c['col']!=0 or c['colspan']>=b['width']:return no('caption_not_partial_left_header')
 novel=[v for v in top if v is not c]
 if any(v['col']<c['colspan'] for v in novel):return no('column_overlap')
 if any(norm(v['text']) in ordered(a,0) for v in novel):return no('new_header_not_new')
 cb=caption['bbox'];cx=(cb[0]+cb[2])/2;cy=(cb[1]+cb[3])/2
 for k,z in enumerate(blocks):
  if k in [owner,j] or z['type']!='table':continue
  v=z['bbox']
  if v[0]<=cx<=v[2] and v[1]<=cy<=v[3]:return no('caption_covered_by_other_table')
 geo=geometry(im,blocks[owner],caption,expanded)
 if not geo['accepted']:return no('source_geometry_reject',geometry=geo)
 return dict(accepted=True,reason='shared_top_row_caption_consumed_once',caption_owner=j,geometry=geo,old_nonempty_cells=len(ordered(a,0)),new_nonempty_cells=len(ordered(b,0)),new_header_text=[v['text'] for v in novel],structural_scope='Use full observed model table; source supports common top row. Body equivalent span encoding is not claimed uniquely determined by image.')
