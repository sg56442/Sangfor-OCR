import json,hashlib,sys,os
from pathlib import Path
from PIL import Image
import torch
from transformers import AutoProcessor
O=Path(os.environ['SPACING_OUT']);torch.set_num_threads(2);p=AutoProcessor.from_pretrained(sys.argv[1],local_files_only=True);rows=json.load(open(O/'plan.json'))
def measure(im,prompt):
 msg=[dict(role='system',content='You are a helpful assistant.'),dict(role='user',content=[dict(type='image',image=im),dict(type='text',text=prompt)])];s=p.apply_chat_template(msg,tokenize=False,add_generation_prompt=True);v=p(text=[s],images=[im],return_tensors='pt');return dict(prompt_tokens=int(v['input_ids'].shape[-1]),tensor_sha256=hashlib.sha256(v['pixel_values'].numpy().tobytes()).hexdigest(),grid=v['image_grid_thw'].tolist())
for q in rows:
 if not q['tasks']:continue
 q['native_processor']=measure(Image.open(O/f'native_{q["index"]}.png'),q['tasks'][0]['prompt'])
 for t in q['tasks']:
  t['processor']=measure(Image.open(O/f'view_{q["index"]}_{t["view"]}_prepared.png'),t['prompt']);assert t['processor']['tensor_sha256']!=q['native_processor']['tensor_sha256'];assert t['processor']['prompt_tokens']+4096<=8192
(O/'processor_plan.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print('PASS',len(rows),'native/2-view tensor and context checks before inference')
