"""Observe native HTTP payloads and replies without modifying requests."""
import hashlib,io,json,os,pathlib,threading,time,base64
from PIL import Image
from mineru_vl_utils.vlm_client.http_client import HttpVlmClient
lock=threading.Lock()
root=pathlib.Path(os.environ['FT1021_AUDIT_DIR']);root.mkdir(parents=True,exist_ok=True)
(root/'images').mkdir(exist_ok=True)
def sha(x):return hashlib.sha256(x).hexdigest()
def emit(row):
 with lock:
  with (root/'http.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False,default=str)+'\n')
original=HttpVlmClient.build_request_body
response_original=HttpVlmClient.get_response_data
def build(self,*args,**kwargs):
 body=original(self,*args,**kwargs);items=[]
 for msg in body['messages']:
  if isinstance(msg['content'],list):
   for part in msg['content']:
    if part['type']=='image_url':
     data=base64.b64decode(part['image_url']['url'].split(',',1)[1]);h=sha(data)
     with Image.open(io.BytesIO(data)) as im:items.append(dict(encoded_sha256=h,pixel_sha256=sha(im.convert('RGB').tobytes()),size=im.size,mode=im.mode))
     dest=root/'images'/f'{h}.png'
     with lock:
      if not dest.exists():dest.write_bytes(data)
 digest=sha(json.dumps(body,sort_keys=True).encode())
 emit(dict(stage='configured',request_sha256=digest,images=items,parameters={k:v for k,v in body.items() if k!='messages'},prompts=[x for m in body['messages'] for x in (m['content'] if isinstance(m['content'],list) else []) if x['type']=='text'],time=time.time()))
 return body
def response(self,r):
 if r.status_code!=200:emit(dict(stage='failed_response',status_code=r.status_code,body=r.text,time=time.time()))
 data=response_original(self,r)
 body=json.loads(r.request.content)
 emit(dict(stage='consumed',request_sha256=sha(json.dumps(body,sort_keys=True).encode()),response=data,time=time.time()))
 return data
HttpVlmClient.build_request_body=build;HttpVlmClient.get_response_data=response
