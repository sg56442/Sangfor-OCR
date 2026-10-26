import sys,json,hashlib,io,os,subprocess
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/research'),str(R/'code/experimenter')]
from boundary_view_0055 import detect,expand
from finite_request_identity_0101_v1 import helper,pix,key,params,MODEL
from mineru_vl_utils.structs import ContentBlock
from spacing_state_0044 import save,sha
O=R/'reports/researcher_phase2_0057/runtime';O.mkdir(parents=True,exist_ok=True);os.environ['SPACING_OUT']=str(O);audit=R/'runs/phase2_pre_final_stability_v1/native/audit/http.jsonl';os.environ['SPACING_NATIVE_AUDIT']=str(audit)
src=R/'runs/phase2_array_label_production_B_first_v1/predictions';manifest=R/'code/runtime/runs/native_full1651_gpu5_v2/pages.json';cfg=dict(inputs=str(src),manifest=str(manifest),native_audit=str(audit),native_inputs=str(R/'runs/phase2_pre_final_stability_v1/native/predictions'),model=MODEL,budget=8,gpu='3');save(O/'inputs.json',cfg)
subprocess.run([sys.executable,str(R/'code/research/shared_header_census_0057.py')],check=True)
census=json.load(open(O.parent/'census.json'));rows=census['rows'];chosen=[q for q in rows if q['input_risk']][:8]
save(O/'census.json',census)
hh=helper();out=[]
for i,q in enumerate(chosen):
 raw=json.load(open(q['raw']));b=raw['blocks'][q['owner']];im=Image.open(q['source']).convert('RGB');view=im.crop(q['expanded']['expanded_box']);view.save(O/f'view_{i}_0_source.png');(O/f'before_{i}.html').write_text(b['content']);ni,_,_,_=hh.prepare_for_extract(im,[ContentBlock(type='table',bbox=b['bbox'],angle=b.get('angle',0))]);native=Image.open(io.BytesIO(ni[0]));native.save(O/f'native_{i}.png');vi,ps,_,_=hh.prepare_for_extract(view,[ContentBlock(type='table',bbox=[0,0,1,1],angle=b.get('angle',0))]);v=Image.open(io.BytesIO(vi[0]));v.save(O/f'view_{i}_0_prepared.png');(O/f'view_{i}_0.bin').write_bytes(vi[0]);t=dict(view=0,prompt=ps[0],identity=key(v.size,pix(v),'table'),pixel_sha256=pix(v),encoded_sha256=sha(O/f'view_{i}_0.bin'),parameters=params('table'));out.append(dict(**{k:v for k,v in {**q,'geometry':q['expanded']}.items() if k not in ['source_sha256','raw_sha256']},index=i,source_sha256=sha(q['source']),raw_sha256=sha(q['raw']),normal='full_domain_input_risk',native_pixel_sha256=pix(native),tasks=[t]))
save(O/'plan.json',out)
for script,args in [('spacing_processor_0043.py',[MODEL]),('spacing_admit_0044.py',[])]:subprocess.run([sys.executable,str(R/'code/research'/script),*args],check=True)
need={t['pixel_sha256'] for q in out for t in q['tasks']};matches=[];nf=0
for root in [R/'runs',R/'reports',R/'code/experimenter/runs']:
 for parent in root.glob('*phase2*'):
  if parent==O.parent:continue
  for f in parent.rglob('http.jsonl'):
   if any(s in str(f).lower() for s in ['aux','ovis','tele','olddb','rapidocr']):continue
   nf+=1
   for line in f.open(errors='replace'):
    try:z=json.loads(line)
    except ValueError:continue
    if z.get('stage')=='configured' and any(v.get('pixel_sha256') in need for v in z.get('images',[])):matches.append(dict(file=str(f),request=z['request_sha256'],pixels=[v['pixel_sha256'] for v in z.get('images',[]) if v.get('pixel_sha256') in need]))
save(O/'dedup.json',dict(historical_exact_pixel_matches=matches,audit_files_scanned=nf,scope='same-model phase2 configured image pixels; no auxiliary observations'));
# D0362 authorizes first sorted risk fresh stability repeat; no other same-view resend.
repeat_pixels={v for m in matches for v in m['pixels']}
for q in out[1:]:
 assert not any(t['pixel_sha256'] in repeat_pixels for t in q['tasks']),'Existing second-risk observation requires explicit0HTTP binding'

binding={str(O/'inputs.json'):sha(O/'inputs.json'),str(manifest):sha(manifest),str(audit):sha(audit),str(O/'processor_plan.json'):sha(O/'processor_plan.json')}
for q in out:binding[q['raw']]=q['raw_sha256'];binding[q['source']]=q['source_sha256']
save(O/'input_binding.json',binding);save(O/'native_binding.json',dict(native_audit=str(audit),sha256=sha(audit)));deps=json.load(open(R/'reports/researcher_phase2_0044/runtime/dependencies.json'));deps={f:sha(f) for f in deps}
for n in ['boundary_view_0055.py','shared_header_prepare_0057_v2.py','shared_header_census_0057.py','shared_header_0056.py','spacing_observe_0046.py','spacing_admission_0046.py']:deps[str(R/'code/research'/n)]=sha(R/'code/research'/n)
save(O/'dependencies.json',deps);print('READY',len(out),len(rows),flush=True)
