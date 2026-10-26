"""Current-source layout groups and scoped ownership. No GT or identity predicates."""
import re,math,unicodedata

def area(b):return max(0,b[2]-b[0])*max(0,b[3]-b[1])
def intersection(a,b):return area([max(a[0],b[0]),max(a[1],b[1]),min(a[2],b[2]),min(a[3],b[3])])
def significant(a,b):return min(a[2],b[2])-max(a[0],b[0])>.003 and min(a[3],b[3])-max(a[1],b[1])>.003
def union(bs):return [min(b[k] for b in bs) if k<2 else max(b[k] for b in bs) for k in range(4)]
def contains(a,b,tol=.003):return all(a[k]-tol<=b[k] for k in [0,1]) and all(a[k]+tol>=b[k] for k in [2,3])
def parse(text,rect,size):
 pattern=r'<\|box_start\|>(\d{3}) (\d{3}) (\d{3}) (\d{3})<\|box_end\|><\|ref_start\|>([a-z_]+)<\|ref_end\|><\|rotate_up\|>'
 rows=[]
 for m in re.finditer(pattern,text):
  b=[int(v)/1000 for v in m.groups()[:4]];assert 0<=b[0]<b[2]<=1 and 0<=b[1]<b[3]<=1
  rows.append(dict(type=m[5],bbox=[(rect[0]+b[0]*(rect[2]-rect[0]))/size[0],(rect[1]+b[1]*(rect[3]-rect[1]))/size[1],(rect[0]+b[2]*(rect[2]-rect[0]))/size[0],(rect[1]+b[3]*(rect[3]-rect[1]))/size[1]]))
 # Reject unparsed boxes/rotation rather than silently dropping model output.
 assert len(rows)==text.count('<|box_start|>') and rows
 return rows

def proposals(layout,native,bands,size):
 rows=[b for b in layout if b['type']=='text' and sum(intersection(b['bbox'],[v[0]/size[0],v[1]/size[1],v[2]/size[0],v[3]/size[1]])>0 for v in bands)>=1];groups=[]
 for b in sorted(rows,key=lambda b:(b['bbox'][1],b['bbox'][0])):
  q=b['bbox'];matches=[]
  for g in groups:
   a=union([x['bbox'] for x in g]);ov=max(0,min(a[2],q[2])-max(a[0],q[0]));gap=max(0,q[1]-a[3],a[1]-q[3])
   if ov>=.65*min(a[2]-a[0],q[2]-q[0]) and min(a[2]-a[0],q[2]-q[0])>=.8*max(a[2]-a[0],q[2]-q[0]) and gap<=.04:matches.append(g)
  if len(matches)==1:matches[0].append(b)
  else:groups.append([b])
 out=[]
 for g in groups:
  box=union([b['bbox'] for b in g]);risk=sum(intersection(box,[b[0]/size[0],b[1]/size[1],b[2]/size[0],b[3]/size[1]])>0 for b in bands)
  if risk<4:continue
  touched=[i for i,b in enumerate(native) if significant(box,b['bbox'])]
  if any(native[i]['type']=='table' for i in touched):continue
  textowners=[i for i in touched if native[i]['type']=='text']
  if any(not contains(box,native[i]['bbox']) for i in textowners):continue
  # Partial existing paragraph may be replaced only when wholly bound to new group.
  if len(textowners)>1:continue
  if any(native[i]['type'] not in ['text','title'] for i in touched):continue
  right=[i for i,b in enumerate(native) if b['type']=='text' and b.get('content') and b['bbox'][0]>=box[2]-.003 and min(b['bbox'][3],box[3])>max(b['bbox'][1],box[1])]
  anchor=min(right,key=lambda i:(native[i]['bbox'][0],native[i]['bbox'][1])) if right else None
  if not textowners and anchor is None:continue
  out.append(dict(source_bbox=box,layout_blocks=g,risk_bands=risk,replace_owners=textowners,insert_before=anchor))
 return sorted(out,key=lambda p:(p['source_bbox'][1],p['source_bbox'][0]))

def subsequence(old,new):
 a=''.join(unicodedata.normalize('NFKC',old).split());b=iter(''.join(unicodedata.normalize('NFKC',new).split()));return all(any(c==d for d in b) for c in a)
