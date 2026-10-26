"""Apply frozen E column assembly using exact current block identity, never page IDs."""
import copy
from column_signature_v1 import assemble

def select_and_apply(blocks,proposals,answers):
 result=copy.deepcopy(blocks);records=[];used=set()
 for p in proposals:
  def matches(b):return b.get('type')=='text' and list(b.get('bbox',[]))==list(p['bbox']) and (b.get('content') or '')==p['native_content']
  matches_at=[i for i,b in enumerate(blocks) if matches(b)]
  rec={'proposal':p['proposal_id'],'prepared_index':p['index'],'accepted':False}
  if len(matches_at)!=1:rec['reason']='missing_or_ambiguous_current_block';records.append(rec);continue
  index=matches_at[0];rec['current_index']=index
  if index in used:rec['reason']='conflicting_proposals';records.append(rec);continue
  g=answers.get(p['proposal_id'],{});keys=sorted((k for k in g if k.startswith('col')),key=lambda k:int(k[3:]));expected=len(p['cuts'])-1
  if keys!=[f'col{i}' for i in range(expected)]:rec['reason']='missing_column_response';records.append(rec);continue
  content,decision=assemble([g[k] for k in keys]);rec.update(decision)
  if content is not None:result[index]['content']=content;used.add(index);rec.update(accepted=True,reason='frozen_signature_selected')
  else:rec['reason']='signature_rejected'
  records.append(rec)
 return result,records
