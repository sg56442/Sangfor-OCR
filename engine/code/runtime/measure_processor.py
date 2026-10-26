"""Replay exact HTTP-consumed image bytes through the pinned server image processor on CPU.
Grid is processor replay, and cross-checked against server-reported prompt token usage.
"""
import argparse,hashlib,json,pathlib,math
import torch,numpy as np
from PIL import Image
from transformers import AutoProcessor
p=argparse.ArgumentParser();p.add_argument('--audit',required=True);p.add_argument('--model',required=True);p.add_argument('--output',required=True);a=p.parse_args();torch.set_num_threads(2)
proc=AutoProcessor.from_pretrained(a.model);root=pathlib.Path(a.audit)
rows=[json.loads(x) for x in (root/'http.jsonl').read_text().splitlines()]
requests={r['request_sha256']:r for r in rows if r['stage']=='configured'}
responses={r['request_sha256']:r for r in rows if r['stage']=='consumed'}
out=[]
for key,r in requests.items():
 if key not in responses:continue
 ims=[Image.open(root/'images'/(x['encoded_sha256']+'.png')).convert('RGB') for x in r['images']]
 prompt=''.join(x['text'] for x in r['prompts'])
 messages=[{'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':[{'type':'image','image':im} for im in ims]+[{'type':'text','text':prompt}]}]
 text=proc.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
 tensors=proc(text=[text],images=ims,return_tensors='pt');grids=tensors['image_grid_thw'].tolist();usage=responses[key]['response'].get('usage',{});token_count=tensors['input_ids'].shape[-1]
 out.append(dict(request_sha256=key,images=r['images'],image_grid_thw=grids,processed_sizes=[[g[2]*14,g[1]*14] for g in grids],visual_tokens=[math.prod(g)//4 for g in grids],processor_pixel_values_sha256=hashlib.sha256(tensors['pixel_values'].numpy().tobytes()).hexdigest(),replay_prompt_tokens=token_count,server_usage=usage,prompt_tokens_match=token_count==usage.get('prompt_tokens'),remaining_context_before_generation=8192-usage.get('prompt_tokens',8192),finish_reasons=[c.get('finish_reason') for c in responses[key]['response']['choices']],evidence='exact consumed bytes replayed in pinned server image; token usage checked'))
 for im in ims:im.close()
pathlib.Path(a.output).write_text(json.dumps(dict(processor_class=type(proc.image_processor).__name__,requests=len(out),all_prompt_counts_match=all(x['prompt_tokens_match'] for x in out),rows=out),indent=2));print(json.dumps({'requests':len(out),'all_prompt_counts_match':all(x['prompt_tokens_match'] for x in out)}))
