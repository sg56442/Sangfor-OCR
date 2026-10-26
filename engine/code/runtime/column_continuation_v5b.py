"""V4 syntax adapter plus full-page whitespace reading-region guard.
Frozen dependencies unchanged; only merge_prev may change.
"""
from column_continuation_v4 import apply as v4_apply
from reading_region_band_v2 import inspect

def apply(image,blocks):
 out,records=v4_apply(image,blocks)
 for r in records:
  if not r['accepted']:continue
  a,b=r['indices'];ev=inspect(image,blocks,a,b);r['reading_region_evidence']=ev
  if ev['blocked']:
   if 'merge_prev' in blocks[b]:out[b]['merge_prev']=blocks[b]['merge_prev']
   else:out[b].pop('merge_prev',None)
   r.update(accepted=False,reason='separate_whitespace_reading_regions')
 return out,records
