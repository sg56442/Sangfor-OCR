"""Remove only paired visible round/square math delimiter sizing, never glyphs."""
import re
DELIM=re.compile(r'\\\(|\\\)|\\\[|\\\]|(?<!\\)\$\$?')
MACROS=set('left right frac sqrt mathrm mathbf mathit mathcal mathbb boldsymbol partial alpha beta gamma delta epsilon varepsilon theta vartheta lambda mu nu pi rho sigma tau phi varphi chi psi omega Gamma Delta Theta Lambda Pi Sigma Phi Psi Omega times cdot div pm mp le leq ge geq neq ne approx equiv sim simeq in notin subset supset subseteq supseteq cup cap sum prod int iint oint infty sin cos tan log ln exp lim min max det overline underline hat bar vec dot ddot prime quad qquad hspace vspace ell ldots cdots vdots ddots to rightarrow leftarrow leftrightarrow uparrow downarrow circ degree percent'.split())
def body(s):
 if any(x in s for x in [r'\begin',r'\end',r'\middle',r'\text',r'\operatorname',r'\tag',r'\label','&',r'\\']):return s,'structured_or_text'
 if any(m.group()[1:] not in MACROS for m in re.finditer(r'\\[A-Za-z]+',s)):return s,'unknown_macro'
 depth=0;stack=[];remove=[];i=0
 while i<len(s):
  if s[i]=='\\':
   m=re.match(r'\\(?:[A-Za-z]+|.)',s[i:])
   if not m:return s,'escape'
   token=m.group();j=i+len(token)
   if token in [r'\left',r'\right']:
    while j<len(s) and s[j].isspace():j+=1
    if j>=len(s) or s[j] not in '()[]':return s,'unsupported_or_invisible_delimiter'
    char=s[j]
    if token==r'\left':
     if char not in '([':return s,'nonopening'
     stack.append((char,depth))
    else:
     if not stack:return s,'unmatched_right'
     char0,d=stack.pop()
     if depth!=d or (char0,char) not in [('(',')'),('[',']')]:return s,'mixed_or_cross_group'
    remove.append((i,i+len(token)))
   i+=len(token);continue
  if s[i]=='{':depth+=1
  elif s[i]=='}':
   depth-=1
   if depth<0:return s,'brace'
  i+=1
 if depth or stack:return s,'unclosed'
 if not remove:return s,'no_sizing'
 out=s
 for a,b in reversed(remove):out=out[:a]+out[b:]
 return out,'paired_visible_size_only'
def transform(text):
 ds=list(DELIM.finditer(text));spans=[];i=0
 while i<len(ds):
  a=ds[i];close={r'\(':r'\)',r'\[':r'\]','$':'$','$$':'$$'}.get(a.group())
  if close is None or i+1>=len(ds) or ds[i+1].group()!=close:return text,[]
  b=ds[i+1];old=text[a.end():b.start()];new,reason=body(old)
  if new!=old:spans.append(dict(start=a.end(),end=b.start(),before=old,after=new,reason=reason))
  i+=2
 out=text
 for x in reversed(spans):out=out[:x['start']]+x['after']+out[x['end']:]
 return out,spans
