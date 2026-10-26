"""Closed-inline-math adapter. Frozen source-flow/list guards unchanged.
Only merge_prev changes; no GT/page/source keys, formula repairs or rewrites.
"""
from column_continuation_inline_base_v1 import apply as base_apply
from column_continuation_v2 import entry_structure
from column_continuation_v3b import flow_evidence

def apply(image,blocks):
 out,records=base_apply(image,blocks)
 for r in records:
  if not r['accepted']:continue
  a,b=r['indices'];ev=[entry_structure(image,blocks[i]) for i in (a,b)];r['entry_structure']=ev
  if any(e['protected'] for e in ev):r.update(accepted=False,reason='independent_entry_structure')
  else:
   flow=flow_evidence(image,blocks,a,b);r['flow_evidence']=flow
   if flow['blocked']:r.update(accepted=False,reason='interrupted_source_reading_flow')
  if not r['accepted']:
   if 'merge_prev' in blocks[b]:out[b]['merge_prev']=blocks[b]['merge_prev']
   else:out[b].pop('merge_prev',None)
 return out,records
