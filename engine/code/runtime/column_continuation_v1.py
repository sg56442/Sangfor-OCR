"""Current-pixel, current-block column rollover; no identity or GT inputs.
Only merge_prev changes. Original strings, order, types and boxes are invariant.
"""
import copy,re
import numpy as np

def lines(image,bbox):
 w,h=image.size;rect=[round(v*s) for v,s in zip(bbox,[w,h,w,h])]
 g=np.asarray(image.crop(rect).convert('L')); ink=g<min(210,float(np.percentile(g,90))-35)
 active=np.flatnonzero(ink.sum(axis=1)>=max(3,g.shape[1]*.012));runs=[]
 for y in active:
  if runs and y<=runs[-1][-1]+2:runs[-1].append(int(y))
  else:runs.append([int(y)])
 out=[]
 for ys in runs:
  xs=np.flatnonzero(ink[min(ys):max(ys)+1].sum(axis=0)>0)
  if len(xs) and max(ys)-min(ys)>=2:out.append([int(xs[0]),min(ys),int(xs[-1])+1,max(ys)+1])
 return {'rect':rect,'size':[g.shape[1],g.shape[0]],'lines':out}

def apply(image,blocks):
 out=copy.deepcopy(blocks);records=[]
 for i in range(1,len(blocks)):
  a,b=blocks[i-1],blocks[i];s=(a.get('content')or'').strip();t=(b.get('content')or'').strip();x,y=a['bbox'],b['bbox'];wa=x[2]-x[0];wb=y[2]-y[0]
  if a['type']!='text' or b['type']!='text' or b.get('merge_prev') or a.get('angle') or b.get('angle'):continue
  if not (wa>0 and wb>0 and .8<wa/wb<1.25 and x[2]<=y[0]+.008 and 0<=y[0]-x[2]<.10 and y[1]<x[1]-.04):continue
  rec={'indices':[i-1,i],'accepted':False,'reason':'boundary_guard'};records.append(rec)
  if len(s)<35 or len(t)<20 or re.search(r'[。！？.!?：:；;]\s*[”’"\']?$',s):continue
  if re.match(r'(?:[A-Z]|\d+[.．、)]|[（(]\d+[）)]|[①-⑳]|第.{1,5}[章节]|[一二三四五六七八九十]+[、．]|[•●■])',t):continue
  if '\\' in s or '\\' in t or '$' in s or '$' in t:rec['reason']='math_or_escape_boundary';continue
  pa,pb=lines(image,x),lines(image,y);rec.update(source_end=pa,source_start=pb)
  la,lb=pa['lines'],pb['lines']
  if len(la)<2 or len(lb)<2:rec['reason']='insufficient_line_evidence';continue
  ha=float(np.median([v[3]-v[1] for v in la]));hb=float(np.median([v[3]-v[1] for v in lb]));rec.update(line_height=[ha,hb])
  if not .75<ha/hb<1.33:rec['reason']='font_scale_mismatch';continue
  # A full terminal line, unindented next-column start and consistent line pitch.
  if la[-1][2]<pa['size'][0]-.8*ha or lb[0][0]>min(v[0] for v in lb)+.6*hb:rec['reason']='short_terminal_or_indented_start';continue
  pitcha=np.median([v[1]-u[1] for u,v in zip(la,la[1:])]);pitchb=np.median([v[1]-u[1] for u,v in zip(lb,lb[1:])]);rec['line_pitch']=[float(pitcha),float(pitchb)]
  if not .75<pitcha/pitchb<1.33:rec['reason']='line_pitch_mismatch';continue
  # Avoid a new heading immediately above the proposed continuation.
  if any(j!=i-1 and j!=i and c['type'] in ('title','table','image','equation') and c['bbox'][0]<y[2] and c['bbox'][2]>y[0] and 0<=y[1]-c['bbox'][3]<2*hb/image.height for j,c in enumerate(blocks)):
   rec['reason']='nearby_protected_object';continue
  out[i]['merge_prev']=True;rec.update(accepted=True,reason='full_line_column_rollover_no_indentation')
 assert len(out)==len(blocks)
 assert all({k:v for k,v in a.items() if k!='merge_prev'}=={k:v for k,v in b.items() if k!='merge_prev'} for a,b in zip(out,blocks))
 return out,records
