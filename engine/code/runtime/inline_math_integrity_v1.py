"""Conservative lexical inline-TeX admission; never rewrites input.
Checks delimiter/brace/required-argument closure, not mathematical truth.
"""
import re
ARGS={**{x:2 for x in ['frac','dfrac','tfrac','binom','dbinom','tbinom','overset','underset','stackrel']},**{x:1 for x in ['sqrt','text','textrm','textbf','mathrm','mathbf','mathit','mathsf','mathtt','mathcal','mathbb','mathfrak','operatorname','overline','underline','widehat','widetilde','hat','tilde','bar','vec','overrightarrow','dot','ddot','boldsymbol']}}
def math_body(s):
 tokens=re.findall(r'\\[A-Za-z]+\*?|\\.|[^\s]',s);pos=0
 def atom(i):
  if i>=len(tokens):raise ValueError('missing_argument')
  t=tokens[i]
  if t=='{':
   j=sequence(i+1,True)
   if j==i+2:raise ValueError('empty_argument')
   return j
  if t in ['}','^','_','&','\\\\']:raise ValueError('invalid_argument')
  if t.startswith('\\'):
   cmd=t[1:].rstrip('*')
   if cmd in ['begin','end','displaymath','displaystyle']:raise ValueError('display_or_environment')
   j=i+1
   if cmd=='sqrt' and j<len(tokens) and tokens[j]=='[':
    j+=1
    while j<len(tokens) and tokens[j]!=']':j=atom(j)
    if j==len(tokens):raise ValueError('unclosed_root_index')
    j+=1
   for _ in range(ARGS.get(cmd,0)):j=atom(j)
   return j
  return i+1
 def sequence(i,group=False):
  while i<len(tokens):
   if tokens[i]=='}':
    if not group:raise ValueError('extra_brace')
    return i+1
   if tokens[i] in ['^','_']:
    if i==0:raise ValueError('script_without_base')
    i=atom(i+1)
   else:i=atom(i)
  if group:raise ValueError('unclosed_brace')
  return i
 try:
  if not tokens:return False,'empty_math'
  sequence(0)
  if tokens.count('\\left')!=tokens.count('\\right'):return False,'left_right_mismatch'
 except ValueError as e:return False,str(e)
 return True,'closed'
def inspect(text):
 spans=[];i=0
 while i<len(text):
  if text.startswith('$$',i) or text.startswith('\\[',i) or text.startswith('\\]',i):return dict(valid=False,reason='display_delimiter',spans=spans)
  if text.startswith('\\(',i) or text[i]=='$':
   start=i;op='\\(' if text.startswith('\\(',i) else '$';close='\\)' if op=='\\(' else '$';i+=len(op);body=i
   while i<len(text):
    if text.startswith(close,i):break
    if text.startswith('\\(',i) or text.startswith('\\[',i) or (text[i]=='$' and close!='$'):return dict(valid=False,reason='nested_or_crossed_math_delimiter',spans=spans)
    if text[i]=='\\':i+=2
    else:i+=1
   if i>=len(text):return dict(valid=False,reason='unclosed_inline_math',spans=spans)
   ok,reason=math_body(text[body:i])
   if not ok:return dict(valid=False,reason=reason,spans=spans)
   i+=len(close);spans.append([start,i]);continue
  if text[i]=='\\':
   if i+1<len(text) and text[i+1] in '$%&#_{}':i+=2;continue
   return dict(valid=False,reason='command_or_close_outside_math',spans=spans)
  i+=1
 return dict(valid=True,reason='closed_inline_or_literal_escape',spans=spans)
