"""Mixed runtime admission; same final timegate protocol as panel0112v2."""
import json
from pathlib import Path
from phase2_final_time_gate_v1 import deadline,sha
from panel_admission_0112_v2 import input_digest
from dependency_lock_0111_v1 import verify

def binding(inputs,manifest,out,budget,gpu,track):
 return dict(inputs=str(inputs),manifest=str(manifest),out=str(out),inputs_sha256=input_digest(inputs),manifest_sha256=sha(manifest),source_hashes={p['image']:sha(p['image']) for p in json.loads(Path(manifest).read_text())},maximum_HTTP=budget,physical_source_cap=2,owner_cap=1,retry=0,gpu=gpu,track=track)
def admitted(root,out,permit_path=None,permit_sha=None,final_mode=False):
 root=Path(root);out=Path(out);load=lambda p:json.loads(Path(p).read_text());b=load(out/'admission_binding.json');frozen=verify(out/'dependencies.json')
 assert not final_mode or permit_path,'Final mode requires explicit RSI permit'
 if permit_path:
  assert permit_sha and sha(permit_path)==permit_sha,'Permit hash mismatch'
  p=load(permit_path);plan=root/'control/final_validation_plan.json';f=load(plan);freeze=(root/f['runtime_freeze']).resolve()
  assert p['final_plan_sha256']==sha(plan),'Final plan changed'
  assert p['runtime_freeze']==str(freeze) and p['runtime_freeze_sha256']==sha(freeze)==f['runtime_freeze_sha256'],'Freeze changed'
  assert all(p['source_hashes'].get(k)==v for k,v in frozen['files'].items()),'Dependency binding incomplete'
 return deadline(root,root/'code/experimenter/mixed_runtime_0117_v3.py',b,permit_path,permit_sha)
