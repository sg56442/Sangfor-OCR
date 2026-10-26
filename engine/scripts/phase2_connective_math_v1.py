"""Existing grammatical connective words separate prose from complete mathematics."""
import argparse,datetime as dt,hashlib,json,re,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/research'),str(ROOT/'code/experimenter')]
from spacing_apply_0046 import span
from repeated_runtime_0048b import patch
from single_model_selective_v1 import hidden,HIDDEN
OPEN=re.compile(r'\\(text|mbox|mathrm)\s*\{')
FORBIDDEN=re.compile(r'\\(?:begin|end|tag|label|color|textcolor|bbox|boxed|underbrace|overbrace|substack|overset|underset)\b')

CONNECTIVES_ZH={'设','令','若','当','又','因为','所以','因此','从而','故','则','即','得','由','解得','同理','显然','时','其中','综上'}
CONNECTIVES_EN={'if','when','where','then','thus','hence','therefore','otherwise','assuming','let','since','so'}
def convert(source):
 wrapped=re.fullmatch(r'\s*\\\[(.*?)\\\]\s*',source,re.S)
 if wrapped is None:return None,'not_one_complete_display'
 s=wrapped.group(1)
 if FORBIDDEN.search(s) or '$' in s or r'\(' in s or r'\[' in s:return None,'nested_or_numbered_environment'
 parts=[];pos=0;cursor=0;depth=0
 while pos<len(s):
  m=OPEN.match(s,pos) if depth==0 else None
  if m:
   if re.search(r'(?:[_^]|\\(?:frac|dfrac|tfrac|sqrt))\s*$',s[:pos]):return None,'prose_is_unbraced_math_argument'
   end=m.end();level=1
   while end<len(s) and level:
    if s[end]=='\\':end+=2;continue
    if s[end]=='{':level+=1
    elif s[end]=='}':level-=1
    end+=1
   if level:return None,'unbalanced_prose'
   prose=s[m.end():end-1]
   if any(c in prose for c in '\\{}$'):return None,'complex_prose_argument'
   if m.group(1)=='mathrm' and not re.search('[\u4e00-\u9fff]',prose):
    pos=m.end();depth=1;continue
   if s[cursor:pos].strip():parts.append(('math',s[cursor:pos].strip()))
   parts.append(('text',prose));cursor=end;pos=end;continue
  if s[pos]=='\\':
   cmd=re.match(r'\\[A-Za-z]+|\\.',s[pos:]);pos+=len(cmd.group()) if cmd else 1;continue
  if s[pos]=='{':depth+=1
  elif s[pos]=='}':depth-=1
  if depth<0:return None,'unbalanced_math'
  pos+=1
 if depth:return None,'unbalanced_math'
 if s[cursor:].strip():parts.append(('math',s[cursor:].strip()))
 prose=''.join(v for k,v in parts if k=='text');math=[v for k,v in parts if k=='math']
 if not math:return None,'no_math_segment'
 # Nominal labels and units remain displays: this rule is scoped to mixed
 # mathematical statements, not every text-bearing mathematical label.
 relation=re.compile(r'(?<!\\)[=<>]|\\(?:approx|sim|simeq|equiv|leq|geq|lt|gt|parallel|perp|in|notin|to|rightarrow|Rightarrow|Leftrightarrow)\b')
 if not any(relation.search(v) for v in math):return None,'nominal_math_label_without_relation'
 tokens=[re.sub(r'[\s,，:：;；.。]', '',v).lower() for k,v in parts if k=='text']
 if not tokens or any(v not in CONNECTIVES_ZH and v not in CONNECTIVES_EN for v in tokens):return None,'not_top_level_discourse_connectives'
 # Quantity names occupying an operand stay in the display. This is a syntax
 # boundary, not a language phrase list or an evaluation-based selection.
 for i,(kind,v) in enumerate(parts):
  if kind!='text':continue
  after=parts[i+1][1].lstrip() if i+1<len(parts) else ''
  before=parts[i-1][1].rstrip() if i else ''
  after=re.sub(r'^\s*(?:\([^()]*\)|\[[^\[\]]*\])?\s*(?:\\[:,;!]|\\(?:quad|qquad)\b|\s)*:?\s*','',after)
  if re.match(r'(?:[=+*/%]|\\(?:times|div|leq|geq|approx|equiv)\b)',after):return None,'text_is_formal_math_operand'
  if re.search(r'(?:[=+*/]|\\(?:times|div|leq|geq|approx|equiv))$',before):return None,'text_is_formal_math_operand'
 for v in math:
  plain=re.sub(r'\\[{}]', '',v)
  if any(plain.count(a)!=plain.count(b) for a,b in [('(',')'),('[',']')]):return None,'cross_prose_parenthesis_scope'
  if len(re.findall(r'\\left\b',v))!=len(re.findall(r'\\right\b',v)):return None,'cross_prose_delimiter_scope'
 # Existing original segments and their order are preserved; only control wrappers move.
 return ' '.join(v if k=='text' else r'\('+v+r'\)' for k,v in parts),'existing_top_level_grammatical_connectives_with_inline_math'
