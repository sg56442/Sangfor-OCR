"""Zero-HTTP column reconstruction with explicit final admission and full byte binding."""
import argparse,datetime,hashlib,json,shutil,time
from pathlib import Path
from PIL import Image
from column_bridge_0147_v2 import proposals,apply
from phase2_final_time_gate_v1 import evaluate
from dependency_lock_0111_v1 import verify
R=Path(__file__).resolve().parents[2]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ENTRIES=['column_bridge_runtime_0147_v3.py','column_bridge_0147_v2.py','column_bridge_0147_v1.py','phase2_final_time_gate_v1.py','dependency_lock_0111_v1.py']
def admit(cfg,binding):
 load=lambda p:json.loads(Path(p).read_text())
 hashes={str(R/'code/experimenter'/p):sha(R/'code/experimenter'/p) for p in ENTRIES}
 permit=None
 assert binding['budget']==0 and binding['retry']==0 and binding['model_calls']==0
 if cfg.get('permit'):
  assert sha(cfg['permit'])==cfg['permit_sha256'];permit=load(cfg['permit'])
 else:
  assert 'sealed' not in binding['inputs'];assert not cfg.get('permit_sha256')
 final=load(R/'control/final_validation_plan.json')
 evaluate(load(R/'control/phase2_plan.json'),load(R/'control/campaign_contract.json'),final,permit,binding,hashes,datetime.datetime.now(datetime.timezone.utc))
 assert sha(cfg['dependency_lock'])==binding['dependency_lock_sha256'];verify(cfg['dependency_lock'])
 if permit:
  f=(R/final['runtime_freeze']).resolve();assert f.is_relative_to(R/'control/freezes')
  assert sha(f)==final['runtime_freeze_sha256']==permit['active_freeze_sha256']
  assert f==(R/permit['active_freeze']).resolve()
  frozen=load(f)['source_hashes']
  for p,h in hashes.items():assert frozen.get(p,frozen.get(str(Path(p).relative_to(R))))==h
 return hashes

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);a=ap.parse_args();cfg=json.loads(Path(a.config).read_text());b=cfg['binding'];t=time.monotonic()
 B=Path(b['inputs']).resolve();O=Path(b['out']).resolve();P=Path(b['pages']).resolve()
 assert O.is_relative_to(R/'runs') and not O.exists() or (O.is_relative_to(R/'runs') and not (O/'receipt.json').exists())
 assert not O.is_relative_to(B) and not B.is_relative_to(O)
 hashes=admit(cfg,b);admission=time.monotonic()-t
 files=sorted((B/'raw').glob('*.json'));assert len(files)==1651
 images={p.stem:p for p in P.iterdir() if p.is_file()};binding={};records=[]
 for p in files:
  m=B/'markdown'/(p.stem+'.md');s=images[p.stem]
  for f in [p,m,s]:binding[str(f)]=sha(f)
  records.append((p,m,s))
 digest=hashlib.sha256(json.dumps([(p.name,binding[str(p)],binding[str(m)],binding[str(s)]) for p,m,s in records]).encode()).hexdigest()
 assert digest==b['input_sha256'];bind_seconds=time.monotonic()-t-admission
 O.mkdir(parents=True,exist_ok=True);copy_start=time.monotonic()
 for v in ['generator','selected']:shutil.copytree(B,O/(v+'_predictions'),dirs_exist_ok=True)
 copy_seconds=time.monotonic()-copy_start;scan=time.monotonic();rows=[]
 for p,m,s in records:
  raw=json.loads(p.read_bytes());md=m.read_bytes().decode()
  with Image.open(s) as im:qs=proposals(raw['blocks'],im)
  if not qs:continue
  row=dict(raw=str(p),source=str(s),proposals=qs,outcomes=[]);rows.append(row)
  changed=False
  for q in qs:
   value,why=apply(raw,md,q);row['outcomes'].append(dict(accepted=value is not None,reason=why))
   if value:raw,md=value;changed=True
  if changed:
   for v in ['generator','selected']:
    (O/(v+'_predictions/raw')/p.name).write_text(json.dumps(raw,ensure_ascii=False,indent=2));(O/(v+'_predictions/markdown')/m.name).write_bytes(md.encode())
 census=time.monotonic()-scan;admit(cfg,b)
 receipt=dict(pages=1651,rows=rows,bindings=binding,input_sha256=digest,source_hashes=hashes,seconds=time.monotonic()-t,admission_seconds=admission,binding_seconds=bind_seconds,copy_seconds=copy_seconds,census_compose_seconds=census,HTTP=0,prompt_tokens=0,completion_tokens=0,GPU_seconds=0,configured=True,triggered=len(rows),applied=sum(x['accepted'] for r in rows for x in r['outcomes']),consumed='No new model input; original native observations only',selected='generator_equals_selected',scored='offline paired separately')
 (O/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in receipt.items() if k not in ['rows','bindings','source_hashes']}))
if __name__=='__main__':main()
