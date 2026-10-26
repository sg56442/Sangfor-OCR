"""Accumulate independent original-byte edits; ambiguous pages fall back intact."""
import json
from phase2_array_label_runtime_v1 import block_spans
from repeated_runtime_0048b import patch
from spacing_apply_0046 import span

def complete(records):
 if len(records)!=1:return None
 r=records[0];choices=r.get('response',{}).get('choices',[])
 if r.get('status')!='COMPLETE' or len(choices)!=1 or choices[0].get('finish_reason')!='stop':return None
 text=r.get('text')
 if not isinstance(text,str) or not text.strip() or choices[0].get('message',{}).get('content')!=text:return None
 return text

def assemble(rb,md,updates):
 try:
  raw=json.loads(rb);sp=block_spans(rb,raw);owners=[i for i,b in updates]
  assert len(owners)==len(set(owners)),'duplicate_owner'
  re=[];me=[]
  for i,b in updates:
   old=raw['blocks'][i].get('content');assert isinstance(old,str) and old,'null_or_empty_owner'
   re.append((*sp[i],json.dumps(b,ensure_ascii=False).encode()));me.append(span(md,old,b['content']))
  return patch(rb,re),patch(md,me),None
 except (AssertionError,ValueError,KeyError,IndexError,TypeError) as e:return rb,md,'ambiguous_page:'+str(e)
