"""Comparison-only prime equivalence; no output rewriting or page/GT inputs."""
import re,html
TOKEN=re.compile(r'\\[A-Za-z]+|\\[^A-Za-z]|[^\s]')
def math_tokens(body):
 ts=TOKEN.findall(body);stack=0
 for t in ts:
  if t=='{':stack+=1
  if t=='}':
   stack-=1
   if stack<0:return None
 if stack:return None
 if any(t.startswith('\\') and t not in {r'\frac',r'\quad',r'\prime'} for t in ts):return None
 def group_end(start):
  if start>=len(ts) or ts[start]!='{':return None
  depth=0
  for j in range(start,len(ts)):
   if ts[j]=='{':depth+=1
   elif ts[j]=='}':
    depth-=1
    if depth==0:return j+1
  return None
 for j,t in enumerate(ts):
  if t==r'\frac':
   end=group_end(j+1)
   if end is None or group_end(end) is None:return None
 parens=[]
 for t in ts:
  if t in ('(', '['):parens.append(t)
  elif t in (')', ']'):
   if not parens or parens.pop()!=({')':'(',']':'['}[t]):return None
 if parens:return None
 out=[];i=0
 while i<len(ts):
  t=ts[i]
  if len(t)==1 and t.isascii() and t.isalpha() and (i==0 or ts[i-1] not in ('_','^')):
   j=i+1;n=0
   while j<len(ts) and ts[j]=="'":n+=1;j+=1
   if not n and j+2<len(ts) and ts[j:j+2]==['^','{']:
    k=j+2
    while k<len(ts) and ts[k]==r'\prime':k+=1
    if k>j+2 and k<len(ts) and ts[k]=='}':n=k-j-2;j=k+1
   if n:
    if j<len(ts) and ts[j] in ('^','_',"'",r'\prime'):return None
    out.extend([t,('PRIME',n)]);i=j;continue
  # A subscript's one character grouping is TeX-equivalent, not arbitrary brace erasure.
  if t=='_' and i+3<len(ts) and ts[i+1]=='{' and len(ts[i+2])==1 and ts[i+2].isalnum() and ts[i+3]=='}':
   out.extend(['_',ts[i+2]]);i+=4;continue
  out.append(t);i+=1
 return out

def cell_key(text):
 text=html.unescape(text);parts=[];pos=0;pattern=re.compile(r'\\\(|\\\[|\$\$|\$|\\\)|\\\]')
 while pos<len(text):
  m=pattern.search(text,pos)
  if not m:parts.append(('TEXT',re.sub(r'\s+','',text[pos:])));break
  # Escaped dollars, closing-only and nested/mixed delimiters are unsupported.
  if m.start()>0 and text[m.start()-1]=='\\':return None
  op=m.group();cl={r'\(':r'\)',r'\[':r'\]','$':'$','$$':'$$'}.get(op)
  if cl is None:return None
  parts.append(('TEXT',re.sub(r'\s+','',text[pos:m.start()])))
  end=pattern.search(text,m.end())
  if end is None or end.group()!=cl:return None
  if end.start()>0 and text[end.start()-1]=='\\':return None
  body=math_tokens(text[m.end():end.start()])
  if body is None:return None
  parts.append(('MATH',op,tuple(body)));pos=end.end()
 return [x for x in parts if x!=('TEXT','')]

def equivalent_tables(left,right):
 from overlap_continuity import parsed
 a,b=parsed(left),parsed(right)
 if not a or not b:return False
 def key(g):
  tokens=[]
  for c in g[0]['cells']:
   k=cell_key(c['text'])
   if k is None:return None
   # Parse each cell independently, but permit structural repartition of complete tokens.
   for token in k:
    if token[0]=='TEXT' and tokens and tokens[-1][0]=='TEXT':tokens[-1]=('TEXT',tokens[-1][1]+token[1])
    else:tokens.append(token)
  return tokens
 x,y=key(a),key(b)
 return x is not None and y is not None and x==y
