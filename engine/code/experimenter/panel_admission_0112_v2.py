"""Explicit RSI permit and deadline-aware observer-only GPU locks."""
import json,hashlib,fcntl,time,datetime
from pathlib import Path
from phase2_final_time_gate_v1 import deadline,sha

def input_digest(inputs):
 h=hashlib.sha256();root=Path(inputs)
 for sub in ['raw','markdown']:
  for p in sorted((root/sub).iterdir()):
   if p.is_file():h.update(str(p.relative_to(root)).encode());h.update(bytes.fromhex(sha(p)))
 return h.hexdigest()
def run_binding(manifest,inputs,out,gpus):
 assert gpus and len(set(gpus))==len(gpus) and set(gpus)<={0,1,3}
 return dict(manifest=str(Path(manifest).resolve()),manifest_sha256=sha(manifest),inputs=str(Path(inputs).resolve()),inputs_sha256=input_digest(inputs),out=str(Path(out).resolve()),gpus=list(gpus),maximum_HTTP=24,physical_source_cap=6,retry=0)
def admitted_deadline(root,out,permit=None,permit_sha=None):
 root=Path(root);out=Path(out);binding=json.loads((out/'admission_binding.json').read_text());entry=root/'code/experimenter/execute_panel_0112_v2.py'
 from dependency_lock_0111_v1 import verify
 frozen=verify(out/'dependencies.json')
 end=deadline(root,entry,binding,permit,permit_sha)
 if permit:
  approved=json.loads(Path(permit).read_text())['source_hashes']
  assert all(approved.get(p)==h for p,h in frozen['files'].items()),'Incomplete permit dependency binding'
  for name in ['code/experimenter/observe_panels_0112_v2.py','code/experimenter/panel_admission_0112_v2.py']:
   p=(root/name).resolve();assert approved.get(str(p))==sha(p),'Observer/admission hash not in explicit RSI permit'
 return end

def wait_lock(path,end,poll_seconds=1):
 handle=Path(path).open('a+')
 try:
  while True:
   assert datetime.datetime.now(datetime.timezone.utc)<end,'GPU lock deadline exceeded'
   try:
    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert datetime.datetime.now(datetime.timezone.utc)<end,'Deadline crossed during lock acquisition'
    return handle
   except BlockingIOError:time.sleep(poll_seconds)
 except BaseException:handle.close();raise
