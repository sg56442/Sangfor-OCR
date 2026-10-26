"""Integration v1: current-run inputs only; frozen A/E/C gates unchanged.
No filesystem, GT, identity routing, or model calls in these pure application functions.
"""
import copy,re
from lxml import html
from mineru_vl_utils.post_process import json2md
from merge_selector import choose_v2,disjoint
from budget_selector import choose as choose_budget
from fraction_selector import choose as choose_fraction
from table_mechanisms import grids
from cell_geometry import ruling_map

def apply_ae(image,blocks,proposals,answers):
 blocks=copy.deepcopy(blocks);accepted=[];decisions=[]
 for p in proposals:
  parts=[answers[k]['html'] for k in p['request_ids']]
  if p['kind']=='merge':ok,sig=choose_v2(blocks,p,parts[0],image)
  else:ok,sig=choose_budget(blocks[p['indices'][0]]['content'],parts,p['signal']['finish_reason'],[answers[k]['http_receipt']['finish_reason'] for k in p['request_ids']],p['signal']['gap_px'])
  decisions.append(dict(rule='AE_V2',kind=p['kind'],original_indices=p['indices'],bbox=p['bbox'],gate=ok,signals=sig,request_ids=p['request_ids']))
  if ok:accepted.append(p)
 selected=[];used=set()
 for p in accepted:
  if p['kind']=='budget_split' and not used.intersection(p['indices']):selected.append(p);used.update(p['indices'])
 selected+=disjoint([p for p in accepted if p['kind']=='merge' and not used.intersection(p['indices'])]);replace={};remove=set()
 for p in selected:
  new=[]
  for bbox,k in zip(p.get('parts',[p['bbox']]),p['request_ids']):
   b=copy.deepcopy(blocks[p['indices'][0]]);b.update(bbox=bbox,content=answers[k]['html']);new.append((b,p['indices']))
  replace[p['indices'][0]]=new;remove.update(p['indices'][1:])
 output=[];origins=[]
 for i,b in enumerate(blocks):
  if i not in remove:
   for new,origin in replace.get(i,[(b,[i])]):output.append(new);origins.append(origin)
 for d in decisions:d['selected']=any(d['request_ids']==p['request_ids'] for p in selected)
 return output,origins,decisions,bool(selected)

def apply_fraction(image,blocks,origins=None):
 blocks=copy.deepcopy(blocks);decisions=[];changed=False;origins=origins if origins is not None else [[i] for i in range(len(blocks))]
 for idx,b in enumerate(blocks):
  if b['type']!='table' or b.get('angle',0):continue
  gs=grids(b.get('content',''))
  if len(gs)!=1 or gs[0]['rows']<2 or gs[0]['width']<2:continue
  x0,y0,x1,y1=b['bbox'];xy=[round(x0*image.width),round(y0*image.height),round(x1*image.width),round(y1*image.height)];roi=image.crop(xy)
  if min(roi.size)<20:continue
  geo=ruling_map(roi,gs[0])
  if not geo['accepted']:continue
  tree=html.fromstring(b['content']);nodes=tree.xpath('.//td|.//th');assert len(nodes)==len(gs[0]['cells']);table_changed=False
  for cell,g,node in zip(gs[0]['cells'],geo['cells'],nodes):
   if not re.fullmatch(r'\s*\d+\s*/\s*\d+\s*',cell['text']):continue
   bx0,by0,bx1,by1=g['pixel_bbox'];crop=image.crop((round(xy[0]+bx0+2),round(xy[1]+by0+2),round(xy[0]+bx1-2),round(xy[1]+by1-2)));candidate,signal=choose_fraction(cell['text'],crop);ok=candidate is not None
   decisions.append(dict(rule='C_NUMERIC_FRACTION_V1',block_index=idx,original_indices=origins[idx],bbox=b['bbox'],row=cell['row'],col=cell['col'],native=cell['text'],candidate=candidate,selected=ok,signals=signal))
   if ok:
    attrs=dict(node.attrib);node.clear();node.attrib.update(attrs);node.text=candidate;table_changed=True
  if table_changed:b['content']=html.tostring(tree,encoding='unicode');changed=True
 return blocks,decisions,changed

def apply_aec(image,native_raw,native_markdown,proposals=(),answers=None):
 image=image.convert('RGB');blocks,origins,ae,ac=apply_ae(image,native_raw['blocks'],proposals,answers or {});blocks,c,cc=apply_fraction(image,blocks,origins)
 result=copy.deepcopy(native_raw);result['blocks']=blocks
 return dict(raw=result,markdown=json2md(blocks) if ac or cc else native_markdown,provenance=ae+c,origins=origins,changed=ac or cc)
