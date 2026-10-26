"""Bounded research or explicitly RSI-permitted active-freeze final admission."""
import json,hashlib,datetime
from pathlib import Path
from phase2_final_time_gate_v1 import evaluate
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ENTRIES=['skew_runtime_0146_v2.py','skew_transport_0146_v2.py','skew_timegate_0146_v2.py','skew_census_0146_v3.py','skew_prepare_0146_v3.py','skew_group_0146_v1.py','skew_select_0146_v1.py','skew_compose_0146_v2.py','phase2_final_time_gate_v1.py']
def source_hashes(root):return {str(Path(root)/'code/experimenter'/p):sha(Path(root)/'code/experimenter'/p) for p in ENTRIES}
def input_hash(inputs,pages):
 inputs=Path(inputs);pages=Path(pages);images={p.stem:p for p in pages.iterdir() if p.is_file()};fs=sorted((inputs/'raw').glob('*.json'));assert len(fs)==1651
 return hashlib.sha256(json.dumps([(p.name,sha(p),sha(inputs/'markdown'/(p.stem+'.md')),sha(images[p.stem])) for p in fs]).encode()).hexdigest()
def check(root,cfg,verify_input=True,now=None):
 root=Path(root);load=lambda p:json.loads(Path(p).read_text());phase=load(root/'control/phase2_plan.json');contract=load(root/'control/campaign_contract.json');final=load(root/'control/final_validation_plan.json');b=cfg['binding'];now=now or datetime.datetime.now(datetime.timezone.utc);hashes=source_hashes(root);permit=None
 assert 0<=b['budget']<=4 and b['source_cap']==4 and b['owner_cap']==1 and b['retry']==0
 assert b['gpu'] in ['0','1','3'] and Path(b['out']).resolve().is_relative_to(root/'runs')
 if cfg.get('permit'):
  assert sha(cfg['permit'])==cfg['permit_sha256'];permit=load(cfg['permit'])
 else:
  assert not cfg.get('permit_sha256');assert 'sealed' not in b['inputs'],'Research cannot read sealed inputs'
 end=evaluate(phase,contract,final,permit,b,hashes,now)
 if permit:
  f=(root/final['runtime_freeze']).resolve();assert f.is_relative_to(root/'control/freezes');assert sha(f)==final['runtime_freeze_sha256']==permit['active_freeze_sha256'];assert str(f)==str((root/permit['active_freeze']).resolve())
  frozen=load(f)['source_hashes']
  for p,h in hashes.items():assert frozen.get(p,frozen.get(str(Path(p).relative_to(root))))==h,'Mechanism not adopted by active freeze'
 assert sha(cfg['dependency_lock'])==b['dependency_lock_sha256']
 from dependency_lock_0111_v1 import verify
 verify(cfg['dependency_lock'])
 if verify_input:assert input_hash(b['inputs'],b['pages'])==b['input_sha256'],'Input/pages byte binding changed'
 leases=load(root/'control/gpu_leases.json');lease=leases[b['gpu']];assert lease['available_for_inference'] and b['service']==dict(endpoint=lease['endpoint'],container_id=lease['container_id'])
 ledger=Path(b['ledger']).resolve();assert ledger.is_relative_to(root) and ledger==Path(cfg['ledger']).resolve()
 state=load(ledger);assert state['maximum']==b['budget'] and state['ledger_id']==b['ledger_id'];assert 0<=state['reserved']<=b['budget']
 return end
