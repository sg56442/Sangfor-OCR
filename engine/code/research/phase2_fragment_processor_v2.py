import json,hashlib,sys,math
from pathlib import Path
from PIL import Image
import torch
from transformers import AutoProcessor
R=Path('/opt/p2t10/engine');O=Path(sys.argv[2]);torch.set_num_threads(2);proc=AutoProcessor.from_pretrained(sys.argv[1]);P=json.load(open(O/'plan.json'));http={}
for line in (Path(sys.argv[3])).read_text().splitlines():
 q=json.loads(line)
 if q['stage']=='configured':
  for im in q['images']:http[im['pixel_sha256']]=q
def helper(im):
 w,h=im.size
 if max(w,h)/min(w,h)>50:
  nw,nh=(w,math.ceil(w/50)) if w>h else (math.ceil(h/50),h);out=Image.new('RGB',(nw,nh),'white');out.paste(im,((nw-w)//2,(nh-h)//2));im=out
 if min(im.size)<28:
  sc=28/min(im.size);im=im.resize((math.ceil(im.width*sc),math.ceil(im.height*sc)),Image.Resampling.BICUBIC)
 return im

def measure(im,kind):
 prompt='\n'+{'table':'Table','equation':'Formula'}.get(kind,'Text')+' Recognition:';msg=[{'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':[{'type':'image','image':im},{'type':'text','text':prompt}]}];txt=proc.apply_chat_template(msg,tokenize=False,add_generation_prompt=True);t=proc(text=[txt],images=[im],return_tensors='pt');g=t['image_grid_thw'][0].tolist()
 return dict(input_size=list(im.size),processed_size=[g[2]*14,g[1]*14],grid=g,visual_tokens=math.prod(g)//4,prompt_tokens=int(t['input_ids'].shape[-1]),pixel_values_sha256=hashlib.sha256(t['pixel_values'].numpy().tobytes()).hexdigest())
for r in P:
 raw=json.load(open(R/r['raw']));original=[]
 with Image.open(r['processor_source_copy']) as source:
  source=source.convert('RGB');w,h=source.size
  for i in r['indices']:
   b=raw['blocks'][i];box=[round(v*(w if k%2==0 else h)) for k,v in enumerate(b['bbox'])];im=helper(source.crop(box));hsh=hashlib.sha256(im.tobytes()).hexdigest();q=http.get(hsh);path=O/f"{r['request_id']}_native_{i}.png";im.save(path)
   original.append(dict(index=i,pixel_sha256=hsh,box=box,image_path=str(path),native_HTTP=q,processor=measure(im,b['type'])))
  im=helper(Image.open(r['image_path']).convert('RGB'));path=O/f"{r['request_id']}_prepared.png";im.save(path);r['image_path']=str(path);r['pixel_sha256']=hashlib.sha256(im.tobytes()).hexdigest();r['original_views']=original;r['processor']=measure(im,'table');r['native_HTTP']=next((x['native_HTTP'] for x in original if x['index']==r['upper']),None);r['duplicate']=False;r['processor_admitted']=r['processor']['prompt_tokens']+4096<=8192 and r['native_HTTP'] is not None and not r['duplicate'];r['all_original_HTTP_bound']=all(x['native_HTTP'] is not None for x in original)
(O/'processor_plan.json').write_text(json.dumps(P,ensure_ascii=False,indent=2));print([(r['request_id'],r['processor_admitted'],r['all_original_HTTP_bound'],r['processor']['prompt_tokens']) for r in P])
