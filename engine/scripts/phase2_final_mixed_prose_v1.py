"""Reconstruct source-bound mixed-statement tails and every raw/Markdown byte."""
import json,time
from pathlib import Path
from phase2_final_runtime_v1 import ROOT,load,sha,verify_hashes
from phase2_mixed_prose_runtime_v1 import transform
RUNNER='scripts/phase2_mixed_prose_runtime_v1.py'

def verify_prose(folder,source,pages,*,frozen=None):
 began=time.monotonic();folder,source,pages=map(lambda p:Path(p).resolve(),[folder,source,pages]);receipt=load(folder/'receipt.json')
 assert receipt['inputs']==str(source) and receipt['pages_manifest']==str(pages) and receipt['pages_manifest_sha256']==sha(pages)
 assert receipt['pages']==1651 and receipt['HTTP']==0 and receipt['GT_hidden'] and receipt['network_disabled']
 deps=load(folder/'dependencies.json');verify_hashes(deps)
 if frozen is not None:assert all(frozen['source_hashes'].get(p)==h for p,h in deps.items())
 manifest=load(pages);names={r['id'] for r in manifest};assert len(manifest)==len(names)==1651
 for sub,ext in [('raw','json'),('markdown','md')]:assert {p.stem for p in (folder/'predictions'/sub).glob('*.'+ext)}==names
 bindings={};records=[];changed=[];owners=0
 for i,p in enumerate(manifest):
  rp,mp=source/'raw'/(p['id']+'.json'),source/'markdown'/(p['id']+'.md');rb,md=rp.read_bytes(),mp.read_bytes()
  bindings[str(rp)]=sha(rp);bindings[str(mp)]=sha(mp)
  nr,nm,decisions=transform(rb,md);n=sum(q['applied'] for q in decisions);owners+=n
  if n:changed.append(i)
  records.append(dict(manifest_index=i,decisions=decisions))
  for sub,path,data in [('raw',rp,nr),('markdown',mp,nm)]:
   target=folder/'predictions'/sub/path.name;assert target.is_file() and not target.is_symlink() and target.read_bytes()==data
 assert bindings==load(folder/'input_binding.json') and records==receipt['records']
 assert changed==receipt['changed_pages'] and owners==receipt['changed_owners']
 return dict(HTTP=0,changed_pages=len(changed),changed_owners=owners,replay_seconds=receipt['wall_seconds'],verification_seconds=time.monotonic()-began)
