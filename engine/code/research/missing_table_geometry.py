"""Native-only grouping of short aligned blocks; no labels or identifiers."""
def proposals(blocks):
 eligible=[(i,b) for i,b in enumerate(blocks) if b['type'] in ('text','title') and not b.get('angle',0) and .005<b['bbox'][3]-b['bbox'][1]<.065 and .015<b['bbox'][2]-b['bbox'][0]<.35]
 rows=[]
 for i,b in sorted(eligible,key=lambda z:z[1]['bbox'][1]):
  y=b['bbox'][1]
  if rows and abs(rows[-1][0]-y)<.006:rows[-1][1].append((i,b))
  else:rows.append((y,[(i,b)]))
 out=[]
 for (ya,a),(yb,b) in zip(rows,rows[1:]):
  if not 3<=len(a)==len(b)<=8 or not .009<yb-ya<.065:continue
  a=sorted(a,key=lambda z:z[1]['bbox'][0]);b=sorted(b,key=lambda z:z[1]['bbox'][0]);cent=lambda z:(z[1]['bbox'][0]+z[1]['bbox'][2])/2
  if max(abs(cent(x)-cent(y)) for x,y in zip(a,b))>.025:continue
  if any(x[1]['bbox'][2]>y[1]['bbox'][0] for row in [a,b] for x,y in zip(row,row[1:])):continue
  inds=[i for i,_ in a+b];bb=[min(z['bbox'][0] for _,z in a+b),min(z['bbox'][1] for _,z in a+b),max(z['bbox'][2] for _,z in a+b),max(z['bbox'][3] for _,z in a+b)]
  other=[i for i,z in enumerate(blocks) if i not in inds and min(bb[2],z['bbox'][2])>max(bb[0],z['bbox'][0]) and min(bb[3],z['bbox'][3])>max(bb[1],z['bbox'][1])]
  if other:continue
  out.append(dict(indices=sorted(inds),bbox=bb,columns=len(a),row_gap=yb-ya,column_center_error=max(abs(cent(x)-cent(y)) for x,y in zip(a,b))))
 return out
