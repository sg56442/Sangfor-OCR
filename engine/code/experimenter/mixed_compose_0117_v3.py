"""Aggregate selected targets per page; preserve unrelated markdown bytes."""
import copy
from mixed_anchor_0115_v2 import select

def compose_page(raw,markdown,items):
 original=raw;result=copy.deepcopy(raw);decisions=[];edits=[];seen=set()
 for ordinal,target,indices,response in items:
  d=dict(ordinal=ordinal,target=target,selected=False)
  if target in seen:d['reason']='duplicate_target';decisions.append(d);continue
  seen.add(target)
  value,reason=select([original['blocks'][i] for i in indices],response.get('text',''),response.get('finish'))
  old=original['blocks'][target].get('content','');needle=old.encode();replacement=value.encode() if value is not None else None
  if value is None:d['reason']=reason
  elif not needle or markdown.count(needle)!=1:d['reason']='markdown_target_not_unique'
  else:
   start=markdown.index(needle);end=start+len(needle)
   if any(start<b and a<end for a,b,_,_ in edits):d['reason']='markdown_target_overlap'
   else:
    edits.append((start,end,replacement,target));result['blocks'][target]['content']=value;d.update(selected=True,reason='unique_context_and_markdown_target',start=start,end=end)
  decisions.append(d)
 output=markdown
 for start,end,value,_ in sorted(edits,reverse=True):output=output[:start]+value+output[end:]
 assert all(b==original['blocks'][i] for i,b in enumerate(result['blocks']) if i not in {x[3] for x in edits})
 return result,output,decisions
