"""Bounded native three-owner context, syntax trigger, conservative target-only extraction."""
import re
from census_mixed_0115_v1 import defects

def context(bs,i):
 if i<1 or i+1>=len(bs):return None
 ids=[i-1,i,i+1];z=[bs[j] for j in ids]
 if any(b['type'] not in ('text','equation') or b.get('angle') for b in z):return None
 for a,b in zip(z,z[1:]):
  x,y=a['bbox'],b['bbox'];h=min(x[3]-x[1],y[3]-y[1]);over=max(0,min(x[2],y[2])-max(x[0],y[0]))
  if not x[1]<y[1] or y[1]-x[3]>.6*h or over<.7*min(x[2]-x[0],y[2]-y[0]):return None
 box=[min(b['bbox'][0] for b in z),min(b['bbox'][1] for b in z),max(b['bbox'][2] for b in z),max(b['bbox'][3] for b in z)]
 for j,b in enumerate(bs):
  if j in ids:continue
  x=b['bbox'];a=max(0,min(x[2],box[2])-max(x[0],box[0]))*max(0,min(x[3],box[3])-max(x[1],box[1]));area=(x[2]-x[0])*(x[3]-x[1])
  if a>.1*area:return None
 return dict(indices=ids,bbox=box)
def triggered(b):
 return b['type']=='text' and bool(set(defects(b.get('content')or''))&{'missing_binary_argument','unterminated_binary_argument','empty_binary_argument'}) and not re.search(r'\\(?:begin|binom)\b',b['content'])
def canon(s):
 s=re.sub(r'\\(?:[A-Za-z]+|[^A-Za-z])','',s)
 return ''.join(re.findall(r'[A-Za-z0-9\u4e00-\u9fff①-⑳]',s)).lower()
def select(original,answer,finish):
 if finish!='stop':return None,'incomplete_response'
 # Require explicit three logical lines; never infer per-owner split from answer words.
 lines=[l.strip() for l in answer.splitlines() if l.strip()]
 if len(lines)!=3:return None,'not_three_explicit_lines'
 if canon(lines[0])!=canon(original[0]['content']) or canon(lines[2])!=canon(original[2]['content']):return None,'context_changed'
 if defects(lines[1]):return None,'broken_candidate'
 old=canon(original[1]['content']);new=canon(lines[1]);it=iter(new)
 if not all(any(c==x for x in it) for c in old):return None,'old_lexical_content_lost'
 if not triggered(original[1]):return None,'normal_control_no_repair'
 return lines[1],'syntax_repaired_context_preserved'
