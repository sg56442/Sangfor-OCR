"""Conservative runtime content invariants; no GT or page features."""
import re

def width_fold(s):
 return ''.join(chr(ord(c)-0xFEE0) if 0xFF01<=ord(c)<=0xFF5E else ' ' if c=='\u3000' else c for c in s)

def semantic_tokens(s):
 return re.findall(r'[A-Za-z]+|\d+(?:\.\d+)?|[^\s]',width_fold(s))

def formula_canonical(s):
 return re.sub(r'\\(?:qquad|quad|left|right)(?![A-Za-z])|\\[\[\],;!]|\s','',s).strip(' ,;')

def independent_formula(s):
 c=formula_canonical(s)
 if re.match(r'^(?:[⇒⇔→⟹⟺]|\\(?:Rightarrow|Leftarrow|Leftrightarrow|Longrightarrow|Longleftarrow|Longleftrightarrow|rightarrow|leftarrow|leftrightarrow|implies|iff|therefore|because))',c):return False
 return ('=' in c and not re.match(r'^(=|[+*/<>]|\\(?:leq|geq|times|div|text\{(?:and|if)))',c)
         and not re.search(r'[=+*/<>-]$',c)
         and all(c.count(x)==c.count(y) for x,y in [('(',')'),('[',']'),('{','}')]))

def redundant_numeric_groups(s):
 """Remove only standalone numeric grouping inside inline math, never command arguments or powers."""
 def math_region(m):
  value=m.group(1)
  def numeric(n):
   before=value[:n.start()].rstrip()
   safe=(not before or before[-1:] in '(,=+-<>' or any(before.endswith(x) for x in [r'\times',r'\cdot',r'\pm']))
   return n.group(1) if safe else n.group(0)
  value=re.sub(r'\{([+-]?\d+(?:\.\d+)?)\}',numeric,value)
  return r'\('+value+r'\)'
 return re.sub(r'\\\((.*?)\\\)',math_region,s,flags=re.S)

def table_semantic_tokens(s):return semantic_tokens(redundant_numeric_groups(s))
