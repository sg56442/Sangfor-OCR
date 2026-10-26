"""V4: reject interval anchors inside broad dark fills, not native topology changes."""
import copy
import cv2
import numpy as np
from table_mechanisms import runs
from mineru_vl_utils.post_process import json2md
from source_column_runtime_api import propose_source_columns, apply_source_columns as apply_v3
VERSION='SOURCE_COLUMNS_V4_REJECT_FILLED_BAND_CENTROID'
def anchor_support(image, decision):
 failures=[]
 for left,right in sorted(set(tuple(m['x_interval']) for m in decision.get('mapped',[]))):
  a=np.asarray(image.crop((left,0,right,image.height)).convert('L'));h,w=a.shape
  lines=cv2.morphologyEx((a<160).astype('uint8'),cv2.MORPH_OPEN,np.ones((1,max(8,round(w*.55))),np.uint8))
  bands=runs(lines.mean(1)>.55)
  anchors=set(y for m in decision['mapped'] if m['x_interval']==[left,right] or tuple(m['x_interval'])==(left,right) for y in m['source_y_interval'] if 0<y<h)
  # Reuse original line clustering tolerance; a broader region is not a located line.
  for y in sorted(anchors):
   for s,e in bands:
    if s<=y<e and e-s>max(3,h*.006):failures.append(dict(x_interval=[left,right],anchor=y,band=[s,e],reason='filled_band_centroid_not_localized_separator'))
 return not failures,failures

def apply_source_columns(image,native_raw,native_markdown,proposals=None,answers=None):
 result=apply_v3(image,native_raw,native_markdown,proposals,answers)
 for d in result['provenance']:
  if d.get('mapped'):
   supported,failures=anchor_support(image.crop(d['source_bbox']),d);d['localized_horizontal_anchors']=supported;d['ambiguous_filled_bands']=failures
   if d['selected'] and not supported:
    d['selected']=False;d['reason']='ambiguous_filled_band_anchor';idx=d['block_index'];result['raw']['blocks'][idx]=copy.deepcopy(native_raw['blocks'][idx])
 result['changed']=any(d['selected'] for d in result['provenance']);result['markdown']=json2md(result['raw']['blocks']) if result['changed'] else native_markdown;result['version']=VERSION
 return result
