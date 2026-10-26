"""Bound RSI final permit; no production clock override and no self-approval."""
import datetime as dt,sys
from pathlib import Path
R=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(R/'code/experimenter'))
from phase2_final_time_gate_v1 import deadline
from panel_admission_0112_v2 import wait_lock
from spacing_state_0044 import load,save,sha
from single_model_selective_v1 import WEIGHT_SHA,MODEL
ENTRY=R/'code/research/spacing_runtime_0046.py'
def binding(out):
 out=Path(out).resolve();c=load(out/'inputs.json')
 assert Path(c['model'])==MODEL and c['gpu'] in ['0','1','3'] and 0<=c['budget']<=16
 for name in ['dependencies','input_binding']:
  for p,h in load(out/(name+'.json')).items():assert sha(p)==h,(name,p)
 return dict(out=str(out),config=c,weight_sha256=WEIGHT_SHA,owner_cap=1,source_cap=4,retry=0,**{n+'_sha256':sha(out/(n+'.json')) for n in ['input_binding','dependencies','native_binding','processor_plan']})
def lane(c,final):
 assert c.get('lane_plan'),'Final lane plan required'
 p=Path(c['lane_plan']).resolve();entries=[x for x in final['repeats'] if (R/x['plan']).resolve()==p];assert len(entries)==1,'Unknown final lane'
 assert sha(p)==entries[0]['plan_sha256'];v=load(p)
 assert c['gpu']==str(v['gpu']),'Wrong lane GPU'
 assert Path(c['native_inputs'])==(R/v['output']/'native/predictions').resolve(),'Wrong lane native'
 assert Path(c['native_audit'])==(R/v['output']/'native/audit/http.jsonl').resolve(),'Wrong lane audit'
 return dict(path=str(p),sha256=sha(p))
def request(out):
 b=binding(out);f=load(R/'control/final_validation_plan.json');ph=load(R/'control/phase2_plan.json');freeze=(R/f['runtime_freeze']).resolve()
 b['lane']=lane(b['config'],f)
 return dict(mode='final_validation',approved=False,approved_by=None,phase=ph['phase'],run_binding=b,source_hashes=load(Path(out)/'dependencies.json'),final_plan_sha256=sha(R/'control/final_validation_plan.json'),runtime_freeze=str(freeze),runtime_freeze_sha256=sha(freeze),not_before=f['start_at'],campaign_deadline=ph['deadline_at'])
def admitted(out,permit=None,permit_sha=None):
 b=binding(out)
 if permit:
  assert permit_sha and sha(permit)==permit_sha,'Wrong permit SHA'
  p=load(permit);expected=request(out)
  for k in ['run_binding','source_hashes','final_plan_sha256','runtime_freeze','runtime_freeze_sha256','not_before','campaign_deadline','phase']:assert p[k]==expected[k],('Permit mismatch',k)
  f=load(R/'control/final_validation_plan.json');assert p['runtime_freeze_sha256']==f['runtime_freeze_sha256']
  b=expected['run_binding']
 return deadline(R,ENTRY,b,permit,permit_sha)
def transport_failure(exc,logs,task,native,model):
 """Only ordinary network failures may continue; inspect any emitted wire first."""
 import httpx
 from table_transport_preflight_0038_v2 import audit_consumed
 for cf in [x for x in logs if x.get('stage')=='configured']:
  assert cf['parameters']==native['parameters'] and cf['prompts']==native['prompts']
  assert cf['images'][0]['pixel_sha256']==task['pixel_sha256']
  for rs in [x for x in logs if x.get('stage')=='consumed']:
   audit_consumed(cf,rs,task,native['parameters']);assert rs['response']['model']==model
   assert rs['request_sha256']==cf['request_sha256']
 consumed=[x for x in logs if x.get('stage')=='consumed']
 if consumed and any(x['response']['choices'][0]['finish_reason']!='stop' for x in consumed):return True
 return isinstance(exc,(httpx.TransportError,TimeoutError,ConnectionError))
