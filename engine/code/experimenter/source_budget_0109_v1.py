"""Atomic transport-attempt caps; source hash is only cost accounting, never content routing."""
import fcntl,json,os

def reserve(path,source_hash,identity,candidate,task):
 with open(path,'r+') as f:
  fcntl.flock(f,fcntl.LOCK_EX);s=json.load(f);reason=None
  if s['reserved']>=s['maximum']:reason='total_cap'
  elif s['by_source'].get(source_hash,0)>=6:reason='physical_source_cap'
  elif identity in s['identities']:reason='duplicate_effective_request'
  elif task in s['by_candidate'].get(str(candidate),[]):reason='candidate_task_cap'
  if reason:
   s['denials'].append(dict(reason=reason,source=source_hash,identity=identity));f.seek(0);json.dump(s,f);f.truncate();f.flush();os.fsync(f.fileno());raise RuntimeError(reason)
  s['reserved']+=1;s['by_source'][source_hash]=s['by_source'].get(source_hash,0)+1;s['identities'].append(identity);s['by_candidate'].setdefault(str(candidate),[]).append(task)
  f.seek(0);json.dump(s,f);f.truncate();f.flush();os.fsync(f.fileno());return s['reserved']
