"""Caller-current API; no filesystem/GT/page identifiers or cached responses."""
import copy
from source_column_runtime_api import propose_source_columns
from native_column_consolidation_v2 import consolidate,VERSION
from mineru_vl_utils.post_process import json2md

def apply_native_column_consolidation(image,native_raw,native_markdown,proposals=None,answers=None):
 proposals=propose_source_columns(image,native_raw) if proposals is None else proposals
 answers=answers or {};result=copy.deepcopy(native_raw);candidate_raw=copy.deepcopy(native_raw);decisions=[]
 for t in proposals:
  idx=t['block_index'];candidate,d=consolidate(native_raw['blocks'][idx]['content'],t,answers)
  if candidate:candidate_raw['blocks'][idx]['content']=candidate
  if candidate and d.get('selected'):result['blocks'][idx]['content']=candidate
  decisions.append(dict(block_index=idx,original_indices=[idx],source_bbox=t['source_bbox'],candidate_available=bool(candidate),**d))
 changed=result!=native_raw;candidate_changed=candidate_raw!=native_raw
 return dict(raw=result,markdown=json2md(result['blocks']) if changed else native_markdown,candidate_raw=candidate_raw,candidate_markdown=json2md(candidate_raw['blocks']) if candidate_changed else native_markdown,provenance=decisions,origins=[[i] for i in range(len(native_raw['blocks']))],changed=changed,candidate_changed=candidate_changed,version=VERSION)
