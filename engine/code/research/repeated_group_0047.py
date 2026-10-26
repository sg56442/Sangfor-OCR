"""Zero-call source-bound repeated-cell ownership probe. No GT or source identities."""
import re,cv2,numpy as np
from spacing_gate_0042 import grid,atoms
from table_mechanisms import runs
from wrapped_view_0045 import transform

def lexical(content):
 g=grid(content)
 if not g or not 3<=g['width']<=12:return []
 cells=g['cells'];matches=list(re.finditer(r'<t[dh]\b[^>]*>([^<]*)</t[dh]>',content,re.I))
 if len(matches)!=len(cells):return []
 by={(c['row'],c['col']):i for i,c in enumerate(cells)};out=[]
 for i,c in enumerate(cells):
  j=by.get((c['row']+1,c['col']))
  if j is None or c['row']==0 or c['col']==0:continue
  d=cells[j];a=matches[i].group(1);b=matches[j].group(1);s=a+b;n=len(s)//2
  if a==b or len(s)%2 or n<8 or s[:n]!=s[n:] or not a or not b:continue
  unit=s[:n]
  if any(n%k==0 and unit==unit[:k]*(n//k) for k in range(1,n)):continue
  rows=[[v for v in cells if v['row']==r] for r in [c['row'],d['row']]]
  if any(v['rowspan']!=1 or v['colspan']!=1 for row in rows for v in row):continue
  numeric=[col for col in range(1,g['width']) if col!=c['col'] and all((r,col) in by and len(atoms(cells[by[r,col]]['text']))==1 for r in [c['row'],d['row']])]
  if not numeric or not all(cells[by[r,0]]['text'] for r in [c['row'],d['row']]):continue
  out.append(dict(rows=[c['row'],d['row']],col=c['col'],numeric=numeric,indices=[i,j],spans=[matches[i].span(1),matches[j].span(1)],unit=unit))
 return out

def source_gate(im,content,c):
 g=grid(content);_,geo=transform(im,content)
 if geo['reason']!='complete_anchor_ending_record_spacing':return dict(accepted=False,reason=geo['reason'])
 col=geo['anchor_column']
 if col not in c['numeric']:return dict(accepted=False,reason='anchor_column_not_numeric')
 h,w=np.asarray(im).shape[:2];xs=[0]+[(s+e)//2 for s,e in geo['gutters']]+[w];gray=np.array(im.convert('L'));m=(gray<180).astype('uint8');hr=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((1,max(30,w//4)),np.uint8));vr=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((max(30,h//3),1),np.uint8));ink=m&~(hr|vr)
 bands=lambda k:[(s,e) for s,e in runs(ink[:,xs[k]:xs[k+1]].sum(1)>0) if s>h*.2 and e-s>=3]
 anchors=bands(col);native=[v for v in g['cells'] if v['col']==col and len(atoms(v['text']))==1]
 if len(anchors)!=len(native):return dict(accepted=False,reason='numeric_count_mismatch')
 index={v['row']:i for i,v in enumerate(native)};reasonbands=bands(c['col']);groups=[]
 for row in c['rows']:
  k=index[row];s,e=anchors[k];tol=max(3,(e-s)*.4);aligned=[z for z in bands(0) if abs(sum(z)/2-(s+e)/2)<=tol]
  if len(aligned)!=1:return dict(accepted=False,reason='left_anchor_ambiguous')
  stop=[i for i,z in enumerate(reasonbands) if abs(sum(z)/2-(s+e)/2)<=tol]
  if len(stop)!=1:return dict(accepted=False,reason='reason_end_not_bound')
  previous=anchors[k-1][1] if k else h*.2
  yy=[z for z in reasonbands[:stop[0]+1] if z[0]>previous]
  if len(yy)<2:return dict(accepted=False,reason='not_complete_multiline_group',groups=groups,bands=yy)
  groups.append(yy)
 if len(groups[0])!=len(groups[1]):return dict(accepted=False,reason='unequal_group_band_count',groups=groups)
 scores=[]
 for aa,bb in zip(*groups):
  crops=[]
  for s,e in [aa,bb]:
   a=gray[s:e,xs[c['col']]:xs[c['col']+1]];ys,xx=np.where(a<180)
   if not len(xx):return dict(accepted=False,reason='empty_glyph_line')
   crops.append(a[ys.min():ys.max()+1,xx.min():xx.max()+1])
  a,b=crops
  if any(abs(x-y)>2 for x,y in zip(a.shape,b.shape)):return dict(accepted=False,reason='glyph_dimensions_differ',groups=groups,dimensions=[list(a.shape),list(b.shape)])
  canvas=np.pad(a,((3,3),(3,3)),constant_values=255);score=float(cv2.matchTemplate(canvas,b,cv2.TM_CCOEFF_NORMED).max());scores.append(score)
 if min(scores)<.98:return dict(accepted=False,reason='complete_glyph_groups_not_equal',scores=scores,groups=groups)
 return dict(accepted=True,reason='unique_repeated_stream_and_complete_source_groups',groups=groups,scores=scores,anchor_column=col,gutters=geo['gutters'])

def candidate(im,content):
 cs=lexical(content)
 if len(cs)!=1:return content,dict(accepted=False,reason='no_unique_string_candidate',lexical=len(cs))
 c=cs[0];d=source_gate(im,content,c)
 if not d['accepted']:return content,dict(d,lexical=1)
 out=content
 for s,e in sorted(c['spans'],reverse=True):out=out[:s]+c['unit']+out[e:]
 assert ''.join(v['text'] for v in grid(out)['cells'] if v['col']==c['col'])==''.join(v['text'] for v in grid(content)['cells'] if v['col']==c['col'])
 return out,dict(d,lexical=1,rows=c['rows'],column=c['col'])
