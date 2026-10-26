"""Explicit final-window exception; diagnostics retain the research drain deadline."""
import datetime as dt,json,hashlib
from pathlib import Path
UTC=dt.timezone.utc
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def evaluate(phase,contract,final,permit,binding,hashes,now):
 if permit is None:
  end=dt.datetime.fromisoformat(phase['drain_by']);assert now<end,'Research drain reached';return end
 assert final['enabled'] is True and final['phase']==phase['phase'],'Final validation not enabled by RSI'
 assert permit['mode']=='final_validation' and permit['approved'] is True and permit['approved_by']=='RSI'
 assert permit['phase']==phase['phase']==contract['phase']
 assert permit['run_binding']==binding,'Final run/input/budget binding mismatch'
 assert all(permit['source_hashes'].get(p)==h for p,h in hashes.items()),'Final entry/time gate source mismatch'
 assert permit['campaign_deadline']==phase['deadline_at']==contract['deadline_at']
 assert permit['not_before']==final['start_at']
 start=dt.datetime.fromisoformat(permit['not_before']);end=dt.datetime.fromisoformat(permit['campaign_deadline'])
 assert start<=now<end,'Outside explicitly admitted final validation window'
 return end

def deadline(root,entry,binding,permit_path=None,permit_sha256=None):
 root=Path(root);load=lambda p:json.loads(Path(p).read_text());permit=None
 if permit_path:
  assert permit_sha256 and sha(permit_path)==permit_sha256,'Explicit final admission SHA mismatch'
  permit=load(permit_path)
 else:assert not permit_sha256,'SHA without final admission'
 hashes={str(Path(entry).resolve()):sha(entry),str(Path(__file__).resolve()):sha(__file__)}
 return evaluate(load(root/'control/phase2_plan.json'),load(root/'control/campaign_contract.json'),load(root/'control/final_validation_plan.json'),permit,binding,hashes,dt.datetime.now(UTC))
