"""Runtime audit of any current complete pure native, including new final roots.
No historical path allowlist. RSI binds the actual producer's prelaunch freeze;
this audit proves retained artifacts, not an invented retrospective code freeze.
"""
import sys,json,dataclasses
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_single_model_inputs_v1 import audit
from single_model_selective_v1 import sha,validate_pages
from mineru_vl_utils.mineru_client import DEFAULT_PROMPTS,DEFAULT_SAMPLING_PARAMS

def verify_native(native,pages_path):
 native=Path(native).resolve();assert native.is_relative_to(ROOT)
 pages=validate_pages(pages_path)
 proof=audit(native,{p['id'] for p in pages})
 for line in (native/'audit/http.jsonl').open():
  row=json.loads(line)
  if row['stage']!='configured':continue
  tasks=[k for k,v in DEFAULT_PROMPTS.items() if row['prompts']==[dict(type='text',text=v)]]
  assert len(tasks)==1, 'Unknown native prompt'
  params=dataclasses.asdict(DEFAULT_SAMPLING_PARAMS[tasks[0]])
  expected={k:params[k] for k in ['temperature','top_p','top_k','presence_penalty','frequency_penalty','repetition_penalty']}
  expected.update(model=proof.get('model', '/opt/p2t10/model'),vllm_xargs=dict(no_repeat_ngram_size=params['no_repeat_ngram_size'],debug=False),skip_special_tokens=False)
  if params['max_new_tokens'] is not None:expected['max_tokens']=params['max_new_tokens']
  assert row['parameters']==expected, 'Non-cc1009 request parameters'
 return dict(native=str(native),pages_sha256=sha(pages_path),audit=proof,
             auditor_sha256=sha(ROOT/'scripts/audit_single_model_inputs_v1.py'),
             producer_freeze_scope='Must be bound by RSI before native launch; not retrospectively asserted')
