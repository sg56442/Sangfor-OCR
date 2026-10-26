import sys,json,time,io,hashlib
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/research'),str(R/'code/experimenter'),str(R/'code/runtime')]
from finite_request_identity_0101_v1 import helper,pix,key,MODEL,params,prompts
from mineru_vl_utils.structs import ContentBlock
from transformers import AutoProcessor
import torch
O=Path(sys.argv[1]);t=time.monotonic();rows=json.load(open(O/'census.json'))['rows'];budget=json.load(open(O/'budget.json'));remaining=budget['maximum']-budget['reserved'];rows=sorted(rows,key=lambda x:(x['source_sha256'],x['owner'],x['row'],x['col']));capped=rows[remaining:];rows=rows[:remaining];out=[];torch.set_num_threads(2);proc=AutoProcessor.from_pretrained(MODEL,local_files_only=True) if rows else None
seen=set()
for q in rows:
 j=q['ordinal'];im=Image.open(O/f'cell{j}.png');data,ps,_,_=helper().prepare_for_extract(im,[ContentBlock(type='text',bbox=[0,0,1,1],angle=0)]);v=Image.open(io.BytesIO(data[0]));msg=[dict(role='system',content='You are a helpful assistant.'),dict(role='user',content=[dict(type='image',image=v),dict(type='text',text=ps[0])])];ss=proc.apply_chat_template(msg,tokenize=False,add_generation_prompt=True);tensor=proc(text=[ss],images=[v],return_tensors='pt');m=dict(prompt_tokens=int(tensor['input_ids'].shape[-1]),grid=tensor['image_grid_thw'].tolist(),tensor_sha256=hashlib.sha256(tensor['pixel_values'].numpy().tobytes()).hexdigest());ident=key(v.size,pix(v),'text');owner=q['source_sha256']+':'+str(q['owner'])
 if m['prompt_tokens']+4096>8192 or owner in seen or budget['owners'].get(owner,0)>=1 or budget['sources'].get(q['source_sha256'],0)>=4 or ident in budget['identities']:capped.append(q);continue
 seen.add(owner);(O/f'prepared{j}.bin').write_bytes(data[0]);v.save(O/f'prepared{j}.png');out.append(dict(**q,prompt=ps[0],parameters=params('text'),pixel_sha256=pix(v),identity=ident,prepared_sha256=hashlib.sha256(data[0]).hexdigest(),processor=m))
(O/'prepared.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));(O/'admission.json').write_text(json.dumps(dict(capped=capped,admitted=len(out)),ensure_ascii=False,indent=2));(O/'prepare_timing.json').write_text(json.dumps(dict(seconds=time.monotonic()-t)))
