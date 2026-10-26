"""Process-safe reservation of every supplemental HTTP transport attempt.
Shared file is inherited by dense native subprocesses. Never alters payloads.
Includes retries: hook is inside MinerU RetryTransport, immediately before network.
Reservations also include network attempts that fail; no success is fabricated.
"""
import fcntl,json,os,time
from pathlib import Path

def reserve(path):
 with open(path,'r+') as f:
  fcntl.flock(f,fcntl.LOCK_EX)
  state=json.load(f)
  if state['reserved']>=state['maximum']:
   state['exhausted']=True;state['denied']+=1
   f.seek(0);json.dump(state,f);f.truncate();f.flush()
   raise RuntimeError('SUPPLEMENTAL_HTTP_BUDGET_EXHAUSTED')
  state['reserved']+=1
  f.seek(0);json.dump(state,f);f.truncate();f.flush()
  return state['reserved']

def install():
 import httpx
 if getattr(httpx.HTTPTransport,'_single_model_budget_installed',False):return
 original=httpx.HTTPTransport.handle_request
 async_original=httpx.AsyncHTTPTransport.handle_async_request
 def counted(request):
  if request.method=='POST' and request.url.path=='/v1/chat/completions':
   reserve(os.environ['FT1021_SUPPLEMENTAL_BUDGET'])
 def handle(self,request):
  counted(request)
  return original(self,request)
 async def async_handle(self,request):
  counted(request)
  return await async_original(self,request)
 httpx.HTTPTransport.handle_request=handle
 httpx.AsyncHTTPTransport.handle_async_request=async_handle
 httpx.HTTPTransport._single_model_budget_installed=True
