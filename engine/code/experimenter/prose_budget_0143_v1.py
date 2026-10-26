"""Persistent mechanism accounting; identities are cost/idempotency keys, not scientific features."""
import json,fcntl,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
LEDGER=Path(os.environ.get('FT1021_PROSE_LEDGER',str(ROOT/'code/experimenter/prose_mechanism_budget_v1.json')))
def reserve(q):
 with LEDGER.open('r+') as f:
  fcntl.flock(f,fcntl.LOCK_EX);s=json.load(f);source=q['source_sha256'];owner=source+':'+str(q['owner']);identity=q['identity']
  assert s['reserved']<s['maximum'],'mechanism cap';assert s['sources'].get(source,0)<4,'source cap';assert s['owners'].get(owner,0)<2,'owner cap';assert identity not in s['identities'],'duplicate effective request'
  s['reserved']+=1;s['sources'][source]=s['sources'].get(source,0)+1;s['owners'][owner]=s['owners'].get(owner,0)+1;s['identities'].append(identity);s['events'].append(dict(source=source,owner=owner,identity=identity,state='reserved_before_wire'));f.seek(0);json.dump(s,f,indent=2);f.truncate();f.flush();os.fsync(f.fileno());return s['reserved']
