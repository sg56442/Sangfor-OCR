"""V2: candidate conservation plus independent RGB separator completeness."""
import numpy as np
from table_mechanisms import runs
from native_column_consolidation import consolidate as generate
VERSION='NATIVE_CELL_SOURCE_COLUMN_CONSOLIDATION_V2_RGB_COMPLETENESS'
def separator_completeness(proposal):
 a=np.asarray(proposal['source_image'].convert('RGB')).astype('int16');h,w=a.shape[:2]
 # RGB difference preserves light chromatic rulings lost by grayscale ink<160.
 support=(np.max(np.abs(a[:,2:]-a[:,:-2]),axis=2)>20).mean(axis=0)
 edges=[(s+e)/2+1 for s,e in runs(support>.5)];bounds=sorted(set(x for pair in proposal['columns'] for x in pair));tol=max(4,w*.01)
 missed=[x for x in edges if min(abs(x-b) for b in bounds)>tol]
 return not missed,dict(rgb_edge_positions=edges,source_column_bounds=bounds,unaccounted_rulings=missed,tolerance=tol)
def consolidate(native,proposal,answers):
 c,d=generate(native,proposal,answers)
 if c:
  ok,evidence=separator_completeness(proposal);d['separator_completeness']=evidence;d['selected']=ok
  if not ok:d['reason']='candidate_rejected_overlooked_chromatic_separator'
 return c,d
