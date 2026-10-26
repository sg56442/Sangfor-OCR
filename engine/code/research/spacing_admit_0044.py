import json,hashlib,os
from pathlib import Path
R=Path(__file__).resolve().parents[2];O=Path(os.environ['SPACING_OUT']);rows=json.load(open(O/'processor_plan.json'));need={q['native_pixel_sha256'] for q in rows};bound={};conf={}
for line in open(Path(os.environ['SPACING_NATIVE_AUDIT'])):
 q=json.loads(line)
 if q['stage']=='configured':
  for im in q.get('images',[]):
   if im['pixel_sha256'] in need:conf[q['request_sha256']]=dict(pixel=im['pixel_sha256'],parameters=q['parameters'],prompts=q['prompts'])
 elif q['stage']=='consumed' and q['request_sha256'] in conf:bound[conf[q['request_sha256']]['pixel']]=dict(request_sha256=q['request_sha256'],**conf[q['request_sha256']])
for q in rows:
 q['native_receipt']=bound[q['native_pixel_sha256']];assert all(t['parameters']==q['native_receipt']['parameters'] for t in q['tasks']);assert q['native_receipt']['parameters']['frequency_penalty']==.005
(O/'processor_plan.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))


identities=[(t['pixel_sha256'],t['prompt'],json.dumps(t['parameters'],sort_keys=True)) for q in rows for t in q['tasks']];assert len(set(identities))==len(identities)
(O/'dedup.json').write_text(json.dumps(dict(within_run_unique=True,historical_repeat_authorization='D0309 second independent native-derived full input'),indent=2));print('bound second input',len(rows))
