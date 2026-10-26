"""Observe native HTTP bodies without changing the frozen client or protocol."""
import hashlib,json,threading
from pathlib import Path
from mineru_vl_utils.vlm_client.http_client import HttpVlmClient

def install(directory):
 root=Path(directory);root.mkdir(parents=True,exist_ok=False);lock=threading.Lock()
 original=HttpVlmClient.get_response_data
 def capture(self,response):
  request=bytes(response.request.content);reply=bytes(response.content)
  rh=hashlib.sha256(request).hexdigest();sh=hashlib.sha256(reply).hexdigest()
  with lock:
   (root/(rh+'.request.bin')).write_bytes(request);(root/(sh+'.response.bin')).write_bytes(reply)
   with (root/'index.jsonl').open('a') as f:f.write(json.dumps(dict(request_sha256=rh,response_sha256=sh,status_code=response.status_code,request_file=rh+'.request.bin',response_file=sh+'.response.bin'))+'\n')
  return original(self,response)
 HttpVlmClient.get_response_data=capture
