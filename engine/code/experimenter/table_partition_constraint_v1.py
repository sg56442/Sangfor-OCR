"""Pixel/native-only closed rectangular partition proposal; never reads labels or GT."""
import numpy as np,cv2

def bands(v):
 d=np.diff(np.r_[False,v,False].astype(int));return [(int(a),int(b)) for a,b in zip(np.where(d==1)[0],np.where(d==-1)[0])]
def detect(image,raw,index):
 b=raw['blocks'][index];w,h=image.size
 if b['type']!='table' or b.get('angle',0)!=0:return dict(eligible=False,reason='not_native_table_or_rotated')
 box=[max(0,round(v*(w if i%2==0 else h))) for i,v in enumerate(b['bbox'])];box[2]=min(w,box[2]);box[3]=min(h,box[3]);x0,y0,x1,y1=box
 rec=dict(eligible=False,reason='small_owner',owner_box=box,index=index,native_type=b['type'])
 if x1-x0<45 or y1-y0<25:return rec
 # Small bounded search only for lines at native box edge; no adaptive expansion.
 search=[max(0,x0-3),max(0,y0-3),min(w,x1+3),min(h,y1+3)]
 a=np.asarray(image.convert('L').crop(search));ink=(a<185).astype('uint8');rh,rw=ink.shape
 H=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(18,rw//8)),np.uint8));V=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((max(16,rh//8),1),np.uint8))
 ys=[(s+e-1)//2 for s,e in bands(H.sum(1)>=max(35,rw*.30))];xs=[(s+e-1)//2 for s,e in bands(V.sum(0)>=max(20,rh*.25))]
 rec.update(line_x=xs,line_y=ys,search_box=search,reason='insufficient_grid_lines')
 if len(xs)<3 or len(ys)<2 or len(xs)>32 or len(ys)>64:return rec
 # Outer extremes must form a single complete rectangle.
 def hedge(y,l,r):return float(H[max(0,y-2):y+3,l:r+1].max(0).mean())
 def vedge(x,t,b):return float(V[t:b+1,max(0,x-2):x+3].max(1).mean())
 outer=[hedge(ys[0],xs[0],xs[-1]),hedge(ys[-1],xs[0],xs[-1]),vedge(xs[0],ys[0],ys[-1]),vedge(xs[-1],ys[0],ys[-1])]
 rec.update(outer_support=outer,reason='open_outer_border')
 if min(outer)<.96:return rec
 nr,nc=len(ys)-1,len(xs)-1
 he=[[hedge(y,xs[c],xs[c+1]) for c in range(nc)] for y in ys]
 ve=[[vedge(x,ys[r],ys[r+1]) for x in xs] for r in range(nr)]
 if any(.10<v<.90 for line in he+ve for v in line):return dict(rec,reason='partial_edge_ambiguous',horizontal_edges=he,vertical_edges=ve)
 parent=list(range(nr*nc))
 def root(i):
  while parent[i]!=i:i=parent[i]
  return i
 def union(a,b):parent[root(a)]=root(b)
 for r in range(nr):
  for c in range(nc):
   if c+1<nc and ve[r][c+1]<.1:union(r*nc+c,r*nc+c+1)
   if r+1<nr and he[r+1][c]<.1:union(r*nc+c,(r+1)*nc+c)
 groups={}
 for r in range(nr):
  for c in range(nc):groups.setdefault(root(r*nc+c),[]).append([r,c])
 cells=[]
 for positions in groups.values():
  rr=[z[0] for z in positions];cc=[z[1] for z in positions];r0,r1,c0,c1=min(rr),max(rr)+1,min(cc),max(cc)+1
  if len(positions)!=(r1-r0)*(c1-c0):return dict(rec,reason='nonrectangular_partition')
  cells.append(dict(row=r0,col=c0,rowspan=r1-r0,colspan=c1-c0,pixel_box=[xs[c0]+search[0],ys[r0]+search[1],xs[c1]+search[0],ys[r1]+search[1]],ink_pixels=int(ink[ys[r0]+3:ys[r1]-2,xs[c0]+3:xs[c1]-2].sum())))
 rect=[xs[0]+search[0],ys[0]+search[1],xs[-1]+search[0]+1,ys[-1]+search[1]+1]
 conflicts=[]
 for j,o in enumerate(raw['blocks']):
  if j==index:continue
  q=[round(v*(w if k%2==0 else h)) for k,v in enumerate(o['bbox'])]
  if min(rect[2],q[2])-max(rect[0],q[0])>2 and min(rect[3],q[3])-max(rect[1],q[1])>2:conflicts.append(j)
 if conflicts:return dict(rec,reason='foreign_owner_overlap',conflicts=conflicts,rect=rect)
 residual=ink.copy();residual[max(0,ys[0]-3):min(rh,ys[-1]+4),max(0,xs[0]-3):min(rw,xs[-1]+4)]=0
 count,lab,stats,_=cv2.connectedComponentsWithStats(residual,8);outside_components=[list(map(int,s)) for s in stats[1:] if s[4]>=6]
 rec.update(eligible=True,reason='closed_partition_diagnostic_only',rect=rect,rows=nr,cols=nc,cells=cells,horizontal_edges=he,vertical_edges=ve,outside_ink_components=outside_components,outside_ink_pixels=int(residual.sum()),unique_owner=True,complete_context=not bool(outside_components),deployment=False)
 return rec
