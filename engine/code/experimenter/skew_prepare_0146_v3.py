import json,sys,hashlib,io,time
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/experimenter'),str(R/'code/runtime')]
from rotation_risk_0146_v1 import risk
from finite_request_identity_0101_v1 import helper,pix,key,MODEL,params,prompts
from mineru_vl_utils.structs import ContentBlock
from dependency_lock_0111_v1 import create
from transformers import AutoProcessor
import torch
O=Path(sys.argv[1]).resolve();census=json.loads((O/'census.json').read_text());rows=[];t=time.monotonic()
for x in sorted(census['rows'],key=lambda x:x.get('source_sha256','')):
 if x['gate']['accepted']:
  rows.append(dict(source=x['source'],raw=x['raw'],owner='complete_text_group',block=dict(type='text',bbox=x['gate']['bbox'],angle=0),gate=x['gate']))
budget=json.loads((O/'budget.json').read_text());remaining=max(0,budget['maximum']-budget['reserved']);capped=rows[remaining:];rows=rows[:remaining];(O/'admission.json').write_text(json.dumps(dict(capped=capped,admitted=len(rows))))
torch.set_num_threads(2);proc=AutoProcessor.from_pretrained(MODEL,local_files_only=True) if rows else None;out=[]
for j,q in enumerate(rows):
 im=Image.open(q['source']).convert('RGB');b=q['block'];rect=[round(v*s) for v,s in zip(b['bbox'],[im.width,im.height]*2)];crop=im.crop(rect);crop.save(O/f'source{j}.png');data,ps,_,_=helper().prepare_for_extract(im,[ContentBlock(type='text',bbox=b['bbox'],angle=0)]);pim=Image.open(io.BytesIO(data[0])).convert('RGB');(O/f'prepared{j}.bin').write_bytes(data[0]);pim.save(O/f'prepared{j}.png')
 msg=[dict(role='system',content='You are a helpful assistant.'),dict(role='user',content=[dict(type='image',image=pim),dict(type='text',text=ps[0])])];s=proc.apply_chat_template(msg,tokenize=False,add_generation_prompt=True);v=proc(text=[s],images=[pim],return_tensors='pt');m=dict(prompt_tokens=int(v['input_ids'].shape[-1]),grid=v['image_grid_thw'].tolist(),tensor_sha256=hashlib.sha256(v['pixel_values'].numpy().tobytes()).hexdigest());
 if m['prompt_tokens']+4096>8192:capped.append(dict(**q,reason='native_context_budget'));continue
 ident=key(pim.size,pix(pim),'text');srcsha=hashlib.sha256(Path(q['source']).read_bytes()).hexdigest()
 if budget['sources'].get(srcsha,0)>=4 or budget['owners'].get(srcsha+':'+str(q['owner']),0)>=1 or ident in budget['identities']:capped.append(dict(**q,reason='persistent_source_owner_or_identity_cap'));continue
 out.append(dict(**q,ordinal=j,source_sha256=hashlib.sha256(Path(q['source']).read_bytes()).hexdigest(),raw_sha256=hashlib.sha256(Path(q['raw']).read_bytes()).hexdigest(),prompt=ps[0],parameters=params('text'),pixel_sha256=pix(pim),identity=key(pim.size,pix(pim),'text'),prepared_size=list(pim.size),prepared_sha256=hashlib.sha256(data[0]).hexdigest(),processor=m,mapping=dict(rect=rect,affine=[crop.width/pim.width,0,rect[0],0,crop.height/pim.height,rect[1]]),causal_change='complete native single-column text group union instead of individually clipped overlapping rows; original pixels, no deskew/no padding sweep'))
(O/'admission.json').write_text(json.dumps(dict(capped=capped,admitted=len(out)),indent=2));(O/'prepared.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));None # shared persistent budget installed by controller after history validation
create(O/'preparation_dependencies.json',['code/experimenter/skew_prepare_0146_v3.py','code/experimenter/skew_census_0146_v3.py','code/experimenter/skew_group_0146_v1.py','code/experimenter/skew_select_0146_v1.py','code/experimenter/skew_compose_0146_v2.py','code/experimenter/skew_transport_0146_v2.py'])
(O/'prepare_timing.json').write_text(json.dumps(dict(seconds=time.monotonic()-t)));print('risk',len(rows),'prepare',time.monotonic()-t)
