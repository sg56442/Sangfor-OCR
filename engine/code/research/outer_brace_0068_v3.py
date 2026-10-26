"""Reattach native paragraph math to a complete source outer brace, zero calls."""
import re,cv2,numpy as np
cv2.setNumThreads(2)
def transform(im,b):
 s=b.get('content')
 if b.get('type')!='text' or not isinstance(s,str) or b.get('angle',0) or s.count('\\begin{cases}')<2 or '\n\n' not in s:return None,'not_multi_cases_text'
 w,h=im.size;box=[round(v*z) for v,z in zip(b['bbox'],[w,h,w,h])];a=np.array(im.convert('L').crop(box));proof=[]
 for threshold in [160,190]:
  n,l,stats,c=cv2.connectedComponentsWithStats((a<threshold).astype('uint8'),8);found=[]
  for x,y,bw,bh,area in stats[1:]:
   if x<a.shape[1]*.05 and bh>a.shape[0]*.85 and bw<a.shape[1]*.04 and y>=1 and y+bh<=a.shape[0]-1:found.append([int(v) for v in [x,y,bw,bh,area]])
  if len(found)!=1:return None,'no_complete_left_outer_brace_component'
  x,y,bw,bh,_=found[0]
  component=(a[y:y+bh,x:x+bw]<threshold)
  def left_at(frac):
   ys=range(max(0,int(bh*frac)-1),min(bh,int(bh*frac)+2));vals=[int(np.flatnonzero(component[z])[0]) for z in ys if component[z].any()];return min(vals) if vals else None
  q1,mid,q3=left_at(.25),left_at(.5),left_at(.75)
  if None in [q1,mid,q3] or min(q1,q3)-mid<max(1,bw*.15):return None,'not_curved_brace_midpoint'
  proof.append(found[0])
 if any(abs(x-y)>2 for x,y in zip(proof[0][:4],proof[1][:4])):return None,'unstable_outer_brace'
 lines=[]
 for paragraph in s.split('\n\n'):
  parts=[];pos=0
  for m in re.finditer(r'\\\((.*?)\\\)',paragraph,re.S):
   prefix=paragraph[pos:m.start()]
   if any(c in prefix for c in '\\{}$'):return None,'ambiguous_literal_prefix'
   if prefix.strip():parts.append('\\text{'+prefix+'}')
   parts.append(m[1]);pos=m.end()
  suffix=paragraph[pos:]
  if any(c in suffix for c in '\\{}$'):return None,'ambiguous_literal_suffix'
  if suffix.strip():parts.append('\\text{'+suffix+'}')
  if not parts:return None,'empty_row'
  lines.append(' '.join(parts))
 new='\\[\\left\\{\\begin{array}{l}'+' \\\\ '.join(lines)+'\\end{array}\\right.\\]'
 return dict(content=new,box=box,proof=proof,rows=len(lines)), 'complete_outer_brace_native_content_conserved'
