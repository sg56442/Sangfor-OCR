"""One CPU-only initialization API. Never issues an RSI permit or makes HTTP."""
import argparse,json,time
from pathlib import Path
from dependency_lock_0111_v1 import create,verify,sha
from panel_admission_0112_v2 import run_binding
R=Path(__file__).resolve().parents[2]
ENTRIES=['code/experimenter/'+n for n in ['initialize_panel_0112_v2.py','execute_panel_0112_v2.py','observe_panels_0112_v2.py','panel_admission_0112_v2.py','panel_current_0110_v1.py','panel_hidden_0110_v2.py']]+['scripts/processor_replay_stream_v1.py','scripts/launch_owned.py']
def initialize(manifest,inputs,out,gpus):
 t=time.monotonic();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
 binding=run_binding(manifest,inputs,out,gpus)
 bp=out/'admission_binding.json'
 if bp.exists():assert json.loads(bp.read_text())==binding,'Binding changed'
 else:bp.write_text(json.dumps(binding,indent=2))
 lock=out/'dependencies.json'
 frozen=verify(lock) if lock.exists() else create(lock,ENTRIES)
 assert frozen['entries']==ENTRIES,'Different dependency entry closure; use a new output'
 assert all(frozen['files'].get(str((R/e).resolve()))==sha(R/e) for e in ENTRIES),'Missing entry in dependency lock'
 hashes={str(Path(p).relative_to(R)):h for p,h in frozen['files'].items() if Path(p).is_relative_to(R)}
 transport={'source_hashes':hashes,'dependency_lock_sha256':sha(lock)}
 p=out/'freeze_transport_v2.json'
 if p.exists():assert json.loads(p.read_text())==transport
 else:p.write_text(json.dumps(transport,indent=2))
 # Structural input checks, no observations or GT. Behavioral regression evidence remains separate.
 pages=json.loads(Path(manifest).read_text());assert isinstance(pages,list)
 for page in pages:
  assert Path(page['image']).is_file()
  raw=Path(inputs)/'raw'/(page['id']+'.json');md=Path(inputs)/'markdown'/(page['id']+'.md')
  assert isinstance(json.loads(raw.read_text())['blocks'],list) and md.is_file()
 receipt={'status':'PASS','scope':'input schema, source availability, bound dependency integrity; no inference or behavioral-test claim','pages':len(pages),'actual_HTTP':0,'dependency_files':len(frozen['files'])}
 (out/'preflight.json').write_text(json.dumps(receipt,indent=2))
 request={'mode':'final_validation','approved':False,'approved_by':None,'run_binding':binding,'source_hashes':frozen['files'],'note':'RSI must set phase/not_before/campaign_deadline and approve explicitly; this is not a permit.'}
 (out/'permit_request.json').write_text(json.dumps(request,indent=2))
 receipt['initialization_seconds']=time.monotonic()-t
 (out/'initialization.json').write_text(json.dumps(receipt,indent=2));return receipt
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',required=True);ap.add_argument('--inputs',required=True);ap.add_argument('--out',required=True);ap.add_argument('--gpus',required=True);a=ap.parse_args()
 print(json.dumps(initialize(a.manifest,a.inputs,a.out,[int(x) for x in a.gpus.split(',')]),indent=2))
