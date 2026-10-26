"""Current-input-only bounded panel pipeline. No historical responses or scoring inputs.
Call census_page on the current image/native blocks, then next_task with only
responses acquired for that current invocation. Transport/budget supplied by caller.
"""
from enclosed_panel_0108_v2 import panels
from panel_relation_0108_v1 import relation_gate
from panel_group_gate_0109_v1 import admit

def census_page(image,raw):
 out=[]
 for p in panels(image,raw['blocks']):
  ok,reason=relation_gate(p,raw,image.size)
  out.append(dict(p,eligible=ok,relation_reason=reason))
 return out

def next_task(candidate,image,responses,observe_normal=False):
 if not candidate['eligible']:return dict(action='FALLBACK',reason=candidate['relation_reason'])
 if candidate['normal'] and not observe_normal:return dict(action='NORMAL_IDENTITY',reason='existing_native_spatial_coverage_no_extra_call')
 if candidate['normal']:
  return dict(action='NORMAL_TEXT',task='text',rect=candidate['rect']) if 'text' not in responses else dict(action='NORMAL_IDENTITY')
 if '[layout]' not in responses:return dict(action='REQUEST',task='[layout]',rect=candidate['rect'])
 ok,reason=admit(responses['[layout]'],candidate,image.crop(candidate['rect']))
 if not ok:return dict(action='FALLBACK',evidence=reason)
 if 'text' not in responses:return dict(action='REQUEST',task='text',rect=candidate['rect'],evidence=reason)
 return dict(action='SELECT_CHILD',evidence=reason)

def select_child(candidate,response,raw,markdown):
 # The fixed minimal selector consumes only this invocation's current response.
 from compose_panels_0108_v2 import select
 return select(candidate,response,raw,markdown)

if __name__=='__main__':
 import argparse,json
 from pathlib import Path
 from PIL import Image
 ap=argparse.ArgumentParser(description='Current-input finite panel planner; no historical lookup. Responses must be from this invocation.')
 ap.add_argument('--image',required=True);ap.add_argument('--raw',required=True);ap.add_argument('--markdown',required=True);ap.add_argument('--responses');ap.add_argument('--out',required=True)
 a=ap.parse_args();im=Image.open(a.image).convert('RGB');raw=json.loads(Path(a.raw).read_text());md=Path(a.markdown).read_text();responses=json.loads(Path(a.responses).read_text()) if a.responses else {};result=[]
 for i,c in enumerate(census_page(im,raw)):
  c['ordinal']=i;rs=responses.get(str(i),{});action=next_task(c,im,rs);row=dict(candidate=c,next=action)
  if action['action']=='SELECT_CHILD':row['selection']=select_child(c,rs['text'],raw,md)
  result.append(row)
 Path(a.out).write_text(json.dumps(dict(candidates=result,original_image_preserved=True,original_blocks_preserved=True,runtime_inputs=['currentimage','currentnative','currentresponses'],budget_contract='transport must atomically reserve total and physicalsource; max6cumulative0108+0109 diagnostic, fresh deployment newledger'),ensure_ascii=False,indent=2))

def run_page(image,raw,markdown,request,source_cost_key,ledger,maximum_new_calls=16,observe_normal=False):
 """Executable fresh finite flow. request(view, task, candidate) returns audited record.
 Caller supplies same-MinerU native transport with atomic global/source reservation.
 ledger is current invocation cost state, never answer cache. Prior responses are
 not accepted. Source key is used only for accounting, never content decisions.
 """
 decisions=[];children=[];used=0
 for i,c in enumerate(census_page(image,raw)):
  c['ordinal']=i;responses={}
  while True:
   action=next_task(c,image,responses,observe_normal)
   if action['action'] in ['REQUEST','NORMAL_TEXT']:
    if used>=maximum_new_calls or ledger.get(source_cost_key,0)>=6:
     action=dict(action='FALLBACK',reason='finite_cost_budget');break
    response=request(image.crop(action['rect']),action['task'],c)
    used+=1;ledger[source_cost_key]=ledger.get(source_cost_key,0)+1
    responses[action['task']]=response
    if response.get('status')!='CONSUMED':action=dict(action='FALLBACK',reason='request_failure_no_retry');break
    continue
   if action['action']=='SELECT_CHILD':
    child,selection=select_child(c,responses['text'],raw,markdown)
    if child:children.append(child)
    action['selection']=selection
   break
  decisions.append(dict(candidate=c,action=action,responses=responses))
 return dict(children=children,decisions=decisions,new_calls=used,original_blocks=raw['blocks'],original_image_preserved=True)
