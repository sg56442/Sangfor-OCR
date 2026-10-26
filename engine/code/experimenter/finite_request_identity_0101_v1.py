"""Offline diagnostic identity reuse only. Never a production router."""
import json,hashlib,io
from pathlib import Path
from PIL import Image
from mineru_vl_utils.mineru_client import MinerUClientHelper,DEFAULT_PROMPTS,DEFAULT_SAMPLING_PARAMS
MODEL='/opt/p2t10/model'
def helper():return MinerUClientHelper('http-client',DEFAULT_PROMPTS,DEFAULT_SAMPLING_PARAMS,(1036,1036),28,50,False,False,False,False,False,False)
def params(task):
 s=DEFAULT_SAMPLING_PARAMS.get(task,DEFAULT_SAMPLING_PARAMS['[default]'])
 return dict(model=MODEL,temperature=s.temperature,top_p=s.top_p,top_k=s.top_k,presence_penalty=s.presence_penalty,frequency_penalty=s.frequency_penalty,repetition_penalty=s.repetition_penalty,vllm_xargs=dict(no_repeat_ngram_size=s.no_repeat_ngram_size,debug=False),skip_special_tokens=False)
def prompts(task):return [dict(type='text',text=DEFAULT_PROMPTS.get(task,DEFAULT_PROMPTS['[default]']))]
def prepare(im,task):
 h=helper();return Image.open(io.BytesIO(h.prepare_for_layout(im))).convert('RGB') if task=='[layout]' else h.resize_by_need(im)
def key(size,pixel,task):return hashlib.sha256(json.dumps(dict(size=list(size),pixel=pixel,prompts=prompts(task),parameters=params(task)),sort_keys=True).encode()).hexdigest()
def pix(im):return hashlib.sha256(im.tobytes()).hexdigest()
def valid_record(r):return r.get('status')=='CONSUMED' and r.get('configured_parameters')==params(r['task']) and r.get('configured_prompts')==prompts(r['task']) and r.get('processor',{}).get('result',{}).get('prompt_tokens_match') and r.get('response',{}).get('model')==MODEL
