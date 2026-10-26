import numpy as np,cv2
from table_mechanisms import runs
from spacing_gate_0042 import grid,atoms,compact,conserve

def bind(im,old,new):
 c=conserve(old,new)
 if not c['accepted']:return c
 if old==new:return dict(accepted=True,reason='identity')
 a,b=grid(old),grid(new);nb=c['body_start'];h,w=np.asarray(im).shape[:2];m=(np.asarray(im.convert('L'))<180).astype('uint8');hr=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((1,max(30,w//2)),np.uint8));vr=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((max(30,h//2),1),np.uint8));ink=m&~(hr|vr)
 gutters=[(s,e) for s,e in runs(ink[int(h*.2):].sum(0)==0) if e-s>=max(3,w*.003) and s>0 and e<w]
 if len(gutters)!=b['width']-1:return dict(accepted=False,reason='source_column_partition_ambiguous',gutters=gutters)
 xs=[0]+[(s+e)//2 for s,e in gutters]+[w];short_rules=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((1,max(30,w//8)),np.uint8));ink=m&~(short_rules|vr);nn,ll,ss,_=cv2.connectedComponentsWithStats(ink,8);keep=np.ones(nn,dtype='uint8');keep[0]=0
 for k in range(1,nn):
  if ss[k,cv2.CC_STAT_WIDTH]>=max(30,w//40) and ss[k,cv2.CC_STAT_WIDTH]>=10*ss[k,cv2.CC_STAT_HEIGHT]:keep[k]=0
 ink=keep[ll];numeric=[]
 for col in range(1,b['width']):
  cs=[v for v in b['cells'] if v['row']>=nb and v['col']==col and compact(v['text'])]
  if len(cs)<3 or not all(len(atoms(v['text']))==1 for v in cs):continue
  yy=runs(ink[int(h*.2):,xs[col]:xs[col+1]].sum(1)>0);yy=[(s+int(h*.2),e+int(h*.2)) for s,e in yy if e-s>=3]
  med=float(np.median([e-s for s,e in yy])) if yy else 0;yy=[(s,e) for s,e in yy if e-s>=max(3,med*.5)]
  if len(yy)<len(cs):return dict(accepted=False,reason='source_numeric_baselines_missing')
  yy=yy[-len(cs):];numeric.append((col,{v['row']:((s+e)/2,e-s) for v,(s,e) in zip(cs,yy)}))
 if len(numeric)<2:return dict(accepted=False,reason='insufficient_independent_numeric_columns')
 # Every numeric row must agree across columns; no numeric bag matching.
 rs=set.intersection(*(set(q) for _,q in numeric));bound={}
 for row in rs:
  ys=[q[row][0] for _,q in numeric];hs=[q[row][1] for _,q in numeric];tol=max(3,float(np.median(hs))*.6)
  if max(ys)-min(ys)>tol:return dict(accepted=False,reason='cross_column_baseline_disagreement')
  bound[row]=dict(y=float(np.median(ys)),tol=tol)
 # Restrict changes to refinement of old complete records, preserving all other rows and no new fields.
 oldrows=[[compact(v['text']) for v in a['cells'] if v['row']==r] for r in range(nb,a['rows'])];newrows=[[compact(v['text']) for v in b['cells'] if v['row']==r] for r in range(nb,b['rows'])];j=0;changed=[]
 for oldrow in oldrows:
  acc=['']*a['width'];start=j
  while j<len(newrows):
   nr=newrows[j]
   if len(nr)!=len(acc):return dict(accepted=False,reason='row_width')
   acc=[x+y for x,y in zip(acc,nr)];j+=1
   if acc==oldrow:break
   if any(not want.startswith(got) for want,got in zip(oldrow,acc)):return dict(accepted=False,reason='record_boundary_crossing')
  if acc!=oldrow:return dict(accepted=False,reason='unmatched_record')
  if j-start>1:changed.extend(range(nb+start,nb+j))
 if j!=len(newrows) or not changed:return dict(accepted=False,reason='not_pure_record_refinement')
 stub=runs(ink[:,xs[0]:xs[1]].sum(1)>0);stub=[((s+e)/2,e-s) for s,e in stub if e-s>=3]
 for r in changed:
  if r not in bound:return dict(accepted=False,reason='changed_record_without_numeric_baseline')
  z=bound[r];near=[v for v in stub if abs(v[0]-z['y'])<=z['tol']]
  if len(near)!=1:return dict(accepted=False,reason='left_label_baseline_not_unique')
 return dict(accepted=True,reason='conserved_record_refinement_with_source_baselines',gutters=gutters,columns=[x for x,_ in numeric],changed_rows=changed,baseline_bindings=bound)
