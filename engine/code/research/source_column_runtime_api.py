"""Frozen caller-current source-column API. No GT, file paths, page/source identity or answer lookup."""
import copy,hashlib
from PIL import Image
from source_column_views import columns,assemble_columns
from source_column_selector_v2 import boundary_support
from overlap_continuity import parsed,textkey
from mineru_vl_utils.post_process import json2md
VERSION='SOURCE_COLUMNS_V3_NATIVE_COSMETIC_PRESERVATION_MINPAD28'
def content_key(s):
 g=parsed(s)
 return textkey(''.join(c['text'] for c in g[0]['cells'])).replace('{','').replace('}','') if g else None

def propose_source_columns(image,native_raw):
 image=image.convert('RGB');out=[]
 for idx,b in enumerate(native_raw['blocks']):
  if b['type']!='table' or b.get('angle') not in (None,0):continue
  box=[round(v*(image.width if j%2==0 else image.height)) for j,v in enumerate(b['bbox'])];roi=image.crop(box);cols,geo=columns(roi)
  if not cols:continue
  inputs=[]
  for ci,(left,right) in enumerate(cols):
   original=roi.crop((left,0,right,roi.height));w,h=original.size;nw,nh=max(28,w),max(28,h);dx,dy=(nw-w)//2,(nh-h)//2;im=Image.new('RGB',(nw,nh),'white');im.paste(original,(dx,dy))
   inputs.append(dict(key=f'{idx}:{ci}',image=im,pixel_sha256=hashlib.sha256(im.tobytes()).hexdigest(),original_image=original,source_x_interval=[left,right],affine=[1,0,dx,0,1,dy]))
  out.append(dict(block_index=idx,source_bbox=box,source_image=roi,columns=cols,geometry=geo,inputs=inputs))
 return out

def apply_source_columns(image,native_raw,native_markdown,proposals=None,answers=None):
 proposals=propose_source_columns(image,native_raw) if proposals is None else proposals;answers=answers or {};result=copy.deepcopy(native_raw);decisions=[];changed=False
 for t in proposals:
  idx=t['block_index'];supplied=[answers.get(x['key']) for x in t['inputs']];candidate=None;decision=dict(reason='missing_or_unfinished_response')
  if all(a and a.get('http_receipt',{}).get('finish_reason')=='stop' for a in supplied):candidate,decision=assemble_columns([x['original_image'] for x in t['inputs']],[a['html'] for a in supplied],t['columns'])
  native=native_raw['blocks'][idx]['content'];preserved=bool(candidate and content_key(candidate)==content_key(native));supported=False;fails=[]
  if candidate:supported,fails=boundary_support(t['source_image'],t['columns'],decision['mapped'])
  selected=preserved and supported;cosmetic=False
  if selected:
   # Preserve full native serialization when only whitespace/format changes.
   # No equality required for structural corrections: differing topology may pass.
   cosmetic=parsed(native)[2]==parsed(candidate)[2]
   if cosmetic:selected=False;decision['reason']='native_cells_unchanged_preserve_original_bytes'
  if selected:result['blocks'][idx]['content']=candidate;changed=True
  decisions.append(dict(block_index=idx,original_indices=[idx],selected=selected,content_preserved=preserved,boundary_supported=supported,cosmetic_only=cosmetic,source_bbox=t['source_bbox'],unsupported=fails,**decision))
 return dict(raw=result,markdown=json2md(result['blocks']) if changed else native_markdown,provenance=decisions,origins=[[i] for i in range(len(result['blocks']))],changed=changed,version=VERSION)
