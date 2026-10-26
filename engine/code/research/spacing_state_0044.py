"""Crash-conservative durable single-lane request ledger. No response selection here."""
import json,os,datetime,hashlib
from pathlib import Path
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(path,obj):
 path=Path(path);tmp=path.with_suffix('.tmp');data=json.dumps(obj,ensure_ascii=False,indent=2).encode()
 with tmp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path);fd=os.open(path.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def load(path):return json.load(open(path))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def claim(state,key,owner,limit):
 if key in state['records']:return False
 if any(r.get('owner')==owner and r['status']!='NOT_ADMITTED' for r in state['records'].values()):raise RuntimeError('owner already attempted')
 used=sum(r['status']!='NOT_ADMITTED' for r in state['records'].values())
 state['records'][key]=dict(owner=owner,status='NOT_ADMITTED' if used>=limit else 'CLAIMED',reason='budget' if used>=limit else None,claimed_at=now(),wall_seconds=None,usage=None)
 return used<limit
def abandon(state):
 for r in state['records'].values():
  if r['status']=='CLAIMED':r.update(status='ABANDONED_UNKNOWN',reason='interrupted claim: never resend or adopt orphan')
 for r in state['invocations']:
  if r['status']=='RUNNING':r['status']='INTERRUPTED_UNKNOWN_WALL'
def audit_rows(path):
 rows=[]
 if Path(path).exists():
  for line in Path(path).read_text().splitlines():
   try:rows.append(json.loads(line))
   except ValueError:continue # partial last audit line is accounted as unknown claim
 return rows
def costs(state,path):
 consumed={}
 for r in audit_rows(path):
  if r.get('stage')=='consumed':consumed[r['request_sha256']]=r
 known=[r.get('response',{}).get('usage') for r in consumed.values()];unknown_responses=sum(not isinstance(v,dict) or 'prompt_tokens' not in v or 'completion_tokens' not in v for v in known)
 recorded={r.get('request_sha256') for r in state['records'].values() if r.get('request_sha256')}
 attempted=[r for r in state['records'].values() if r['status']!='NOT_ADMITTED']
 return dict(durable_attempts=len(attempted),consumed_responses=len(consumed),known_prompt_tokens=sum(v.get('prompt_tokens',0) for v in known if isinstance(v,dict)),known_completion_tokens=sum(v.get('completion_tokens',0) for v in known if isinstance(v,dict)),unknown_usage_responses=unknown_responses,claims_without_consumed_response=max(0,len(attempted)-len(consumed)),orphan_consumed_requests=sorted(set(consumed)-recorded),unknown_attempt_usage=[k for k,r in state['records'].items() if r['status']!='NOT_ADMITTED' and r.get('usage') is None],known_invocation_wall_seconds=sum(v['wall_seconds'] for v in state['invocations'] if v.get('wall_seconds') is not None),unknown_wall_invocations=sum(v.get('wall_seconds') is None for v in state['invocations']),invocations=state['invocations'])
