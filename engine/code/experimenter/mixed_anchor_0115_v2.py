"""Exposed-response parser revision: unique context anchors; no GT, no inference."""
import re
from mixed_context_0115_v1 import triggered,canon
from census_mixed_0115_v1 import defects

def projection(s):
 keep=[i for i,c in enumerate(s) if not c.isspace() and c not in '{}']
 return ''.join(s[i] for i in keep),keep

def select(original,answer,finish):
 if finish!='stop':return None,'incomplete_response'
 a,positions=projection(answer);left,_=projection(original[0]['content']);right,_=projection(original[2]['content'])
 if not left or not right or a.count(left)!=1 or a.count(right)!=1:return None,'nonunique_context'
 if not a.startswith(left) or not a.endswith(right) or len(left)+len(right)>=len(a):return None,'context_changed'
 start=positions[len(left)];stop=positions[len(a)-len(right)];middle=answer[start:stop].strip()
 if not (middle.startswith(r'\(') and r'\)' in middle) or middle.count(r'\(')!=middle.count(r'\)'):return None,'incomplete_math_boundary'
 if defects(middle):return None,'broken_candidate'
 old=canon(original[1]['content']);new=canon(middle);it=iter(new)
 if not all(any(c==x for x in it) for c in old):return None,'old_lexical_content_lost'
 if not triggered(original[1]):return None,'normal_control_no_repair'
 return middle,'unique_context_target_only'

def fixtures():
 orig=[dict(type='text',content=r'Left \(x\)'),dict(type='text',content=r'\(\frac{a\)'),dict(type='text',content=r'Right \({z}\)')]
 ans=r'Left \(x\) \(\frac{a}{b}\) Right \(z\)'
 assert select(orig,ans,'stop')[0]==r'\(\frac{a}{b}\)'
 assert select(orig,ans+ans,'stop')[0] is None
 assert select(orig,ans.replace('Right','Wrong'),'stop')[0] is None
 assert select(orig,ans.replace(r'\frac{a}{b}',r'\frac{c}{b}'),'stop')[0] is None
 assert select(orig,ans,'length')[0] is None
 assert select(orig,ans.replace(r'\frac{a}{b}',r'\frac{a}{'),'stop')[0] is None
 return 6
if __name__=='__main__':print(fixtures())
