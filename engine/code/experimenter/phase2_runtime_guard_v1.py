"""Read-only binding to RSI-owned phase2 ckpt-58 services; no lifecycle actions."""
import hashlib,json,subprocess,urllib.request
from pathlib import Path
R=Path(__file__).resolve().parents[2]
MODEL='/opt/p2t10/model'
WEIGHT='01dcb5addfa1d6133fd0930e79fa2484817cb0228af21cb4917fa73d04fa3147'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def guard(gpu):
 assert str(gpu) in ('0','1','3')
 lease=load(R/'control/gpu_leases.json')[str(gpu)]
 assert lease['state']=='READY' and lease['service_running'] and lease['available_for_inference']
 assert lease['phase']=='phase2_single_model_97p2' and lease['role']=='RSI'
 assert lease['endpoint']==f'http://127.0.0.1:{28021+100*int(gpu)}'
 baseline=load(R/'evidence/model_baseline.json')
 assert baseline['checkpoint']==MODEL and baseline['model_weight_sha256']==WEIGHT
 ownerpath=R/'code/runtime'/(lease['container']+'.ownership.json');owner=load(ownerpath)
 svc=json.loads(subprocess.check_output(['docker','inspect',lease['container']],text=True))[0]
 assert owner['returncode']==0 and svc['Id']==owner['stdout'].strip()==lease['container_id']
 assert svc['State']['Running'] and 'MODEL='+MODEL in svc['Config']['Env']
 assert any(m['Destination']==MODEL and m['RW'] is False for m in svc['Mounts'])
 view=R/('code/runtime/model-view-'+lease['endpoint'].rsplit(':',1)[1]+'-'+lease['container'])
 assert view.is_dir() and (view/'model.safetensors').resolve()==Path(MODEL)/'model.safetensors'
 processor_hashes={str(f):sha(f) for f in view.iterdir() if f.suffix in ('.json','.jinja','.txt')}
 with urllib.request.urlopen(lease['endpoint']+'/v1/models',timeout=10) as response: api=json.load(response)
 assert MODEL in [m['id'] for m in api['data']]
 return dict(processor_model_view=str(view),processor_hashes=processor_hashes,lease=lease,container_id=svc['Id'],ownership_sha256=sha(ownerpath),model_api=api,model=MODEL,weight_sha256=WEIGHT,weight_evidence='Immutable baseline + RSI-owned service MODEL and read-only checkpoint mount; no fresh weight hashing',read_only_checkpoint_mount=True)
