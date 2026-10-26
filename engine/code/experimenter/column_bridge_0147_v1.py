"""Input-only image-interrupted parallel native column chains; no lexical routing."""
import math

def proposals(bs):
 out=[]
 for ii,im in enumerate(bs):
  if im.get('type') not in ['image','image_block']:continue
  box=im.get('bbox');x,y,X,Y=box
  if X-x<.3 or not .06<Y-y<.35:continue
  text=[(i,b) for i,b in enumerate(bs) if b.get('type') in ['text','title'] and isinstance(b.get('content'),str) and b['content'].strip() and b.get('angle',0)==0]
  below=[(i,b) for i,b in text if Y<=b['bbox'][1]<=Y+.04 and b['bbox'][0]>=x-.025 and b['bbox'][2]<=X+.025 and .07<=b['bbox'][2]-b['bbox'][0]<=.3]
  cols=[]
  for i,b in sorted(below,key=lambda z:z[1]['bbox'][0]):
   l,t,r,z=b['bbox']
   if any(abs(l-c[0])<.02 for c in cols):continue
   above=[(j,a) for j,a in text if a['bbox'][3]<=y and y-a['bbox'][3]<=.03 and abs(a['bbox'][0]-l)<=.025 and abs(a['bbox'][2]-r)<=.025]
   if above:cols.append([l,r])
  if len(cols)<2 or any(a[1]>=b[0] for a,b in zip(cols,cols[1:])):continue
  assigned={}
  for i,b in text:
   bb=b['bbox'];matches=[k for k,(l,r) in enumerate(cols) if bb[0]>=l-.025 and bb[2]<=r+.025 and (bb[3]<=y or bb[1]>=Y)]
   if len(matches)==1:assigned[i]=matches[0]
  if not assigned:continue
  lo=min(assigned);hi=max(assigned)
  # Full contiguous source region must contain no different textual scope or tables.
  if any(i not in assigned and b.get('content') and b.get('type')!='image_caption' for i,b in enumerate(bs) if lo<=i<=hi):continue
  if any(b.get('type') in ['table','equation'] for b in bs[lo:hi+1]):continue
  if any(i!=ii and b.get('type') in ['image','image_block'] for i,b in enumerate(bs) if lo<=i<=hi):continue
  old=sorted(assigned);new=sorted(old,key=lambda i:(assigned[i],bs[i]['bbox'][1]))
  if old==new:continue
  out.append(dict(image=ii,columns=cols,old=old,new=new,lo=lo,hi=hi))
 return out

def apply(raw,md,q):
 import copy
 bs=raw['blocks'];spans=[]
 for i in range(q['lo'],q['hi']+1):
  c=bs[i].get('content')
  if not c:continue
  if not isinstance(c,str) or md.count(c)!=1:return None,'nonunique_owner_MD'
  at=md.index(c);spans.append((at,at+len(c),i))
 if not spans or [i for _,_,i in sorted(spans)]!=[i for _,_,i in spans]:return None,'MD_order_disagrees'
 for (_,end,_),(start,_,_) in zip(spans,spans[1:]):
  if md[end:start].strip():return None,'nonowner_bytes_between'
 start=spans[0][0];end=spans[-1][1];r=copy.deepcopy(raw);mapping=dict(zip(q['old'],q['new']))
 for i,j in mapping.items():r['blocks'][i]=copy.deepcopy(bs[j])
 text='\n\n'.join(r['blocks'][i]['content'] for _,_,i in spans)
 assert sorted(repr(x) for x in bs)==sorted(repr(x) for x in r['blocks'])
 return (r,md[:start]+text+md[end:]),'source_column_chains'
