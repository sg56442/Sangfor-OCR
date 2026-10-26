"""General lossless top-level prose/math serialization; no GT, page routing or inference."""
import argparse,datetime as dt,hashlib,json,re,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/research'),str(ROOT/'code/experimenter')]
from spacing_apply_0046 import span
from repeated_runtime_0048b import patch
from single_model_selective_v1 import hidden,HIDDEN
OPEN=re.compile(r'\\(text|mbox|mathrm)\s*\{')
FORBIDDEN=re.compile(r'\\(?:begin|end|tag|label|color|textcolor|bbox|boxed|underbrace|overbrace|substack|overset|underset)\b')

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
 if len(re.findall('[\u4e00-\u9fff]',prose))<4 and len(re.findall(r'[A-Za-z]{3,}',prose))<4:return None,'insufficient_prose'
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
 return ' '.join(v if k=='text' else r'\('+v+r'\)' for k,v in parts),'top_level_existing_prose_with_inline_math'

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--inputs',required=True);ap.add_argument('--pages',required=True);ap.add_argument('--out',required=True);ap.add_argument('--census-only',action='store_true');ap.add_argument('--isolated',action='store_true');a=ap.parse_args()
 if not a.isolated:
  subprocess.run(hidden(['unshare','--net',sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--isolated']),check=True);return
 assert all(Path(p).stat().st_size==0 for p in HIDDEN)
 src,out=Path(a.inputs).resolve(),Path(a.out).resolve();assert src.is_relative_to(ROOT) and out.is_relative_to(ROOT) and not out.exists();out.mkdir(parents=True)
 pages=json.loads(Path(a.pages).read_text());assert len(pages)==1651
 if not a.census_only:
  for kind in ['raw','markdown']:(out/'predictions'/kind).mkdir(parents=True)
 records=[];files=[];owners=0
 for p in pages:
  rp,mp=(src/'raw'/(p['id']+'.json'),src/'markdown'/(p['id']+'.md'));rb,md=rp.read_bytes(),mp.read_bytes();raw=json.loads(rb);edits=[];changed=[]
  for i,b in enumerate(raw['blocks']):
   if b['type']!='equation' or not b.get('content'):continue
   owners+=1;new,reason=convert(b['content'])
   if new is None:continue
   item=dict(page=p['id'],owner=i,bbox=b['bbox'],source=p['image'],before=b['content'],after=new,reason=reason,applied=False)
   try:
    start,end,text=span(md,b['content'],new)
    assert not any(start<e and end>s for s,e,_ in edits),'overlapping owners'
   except AssertionError as error:item.update(reason='ambiguous_markdown_binding',detail=str(error))
   else:
    edits.append((start,end,text));changed.append(i);item['applied']=True;b.update(type='text',content=new)
   records.append(item)
  if not a.census_only:
   for sub,f,data in [('raw',rp,json.dumps(raw,ensure_ascii=False,indent=2).encode() if changed else rb),('markdown',mp,patch(md,edits))]:
    dst=out/'predictions'/sub/f.name
    if not changed:__import__('os').link(f,dst)
    else:dst.write_bytes(data)
  files.append(dict(page=p['id'],raw_sha256=hashlib.sha256(rb).hexdigest(),md_sha256=hashlib.sha256(md).hexdigest(),changed_owners=changed))
 report=dict(at=dt.datetime.now(dt.timezone.utc).isoformat(),scope='Representation-only exploratory candidate, not production accepted. GT hidden; zero HTTP. All triggers from current native syntax.',inputs=str(src),pages=1651,equation_owners=owners,proposal_owners=len(records),applied_owners=sum(x['applied'] for x in records),changed_pages=sum(bool(x['changed_owners']) for x in files),HTTP=0,census_only=a.census_only,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),records=records,files=files)
 (out/'receipt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print({k:v for k,v in report.items() if k not in ['records','files']})
if __name__=='__main__':main()
