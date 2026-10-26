import sys,json,hashlib,io,os,subprocess
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/research'),str(R/'code/experimenter')]
from boundary_view_0055 import detect,expand
from finite_request_identity_0101_v1 import helper,pix,key,params,MODEL
from mineru_vl_utils.structs import ContentBlock
from spacing_state_0044 import save,sha
O=Path(os.environ['SPACING_OUT']);cfg=json.load(open(O/'inputs.json'));audit=Path(cfg['native_audit']);os.environ['SPACING_NATIVE_AUDIT']=str(audit);src=Path(cfg['inputs']);manifest=Path(cfg['manifest'])
subprocess.run([sys.executable,str(R/'code/research/shared_header_census_0058.py')],check=True)
census=json.load(open(O/'census.json'));rows=census['rows'];chosen=[q for q in rows if q['input_risk']][:cfg['budget']]
save(O/'census.json',census)
hh=helper();out=[]
for i,q in enumerate(chosen):
 raw=json.load(open(q['raw']));b=raw['blocks'][q['owner']];im=Image.open(q['source']).convert('RGB');view=im.crop(q['expanded']['expanded_box']);view.save(O/f'view_{i}_0_source.png');(O/f'before_{i}.html').write_text(b['content']);ni,_,_,_=hh.prepare_for_extract(im,[ContentBlock(type='table',bbox=b['bbox'],angle=b.get('angle',0))]);native=Image.open(io.BytesIO(ni[0]));native.save(O/f'native_{i}.png');vi,ps,_,_=hh.prepare_for_extract(view,[ContentBlock(type='table',bbox=[0,0,1,1],angle=b.get('angle',0))]);v=Image.open(io.BytesIO(vi[0]));v.save(O/f'view_{i}_0_prepared.png');(O/f'view_{i}_0.bin').write_bytes(vi[0]);t=dict(view=0,prompt=ps[0],identity=key(v.size,pix(v),'table'),pixel_sha256=pix(v),encoded_sha256=sha(O/f'view_{i}_0.bin'),parameters=params('table'));out.append(dict(**{k:v for k,v in {**q,'geometry':q['expanded']}.items() if k not in ['source_sha256','raw_sha256']},index=i,source_sha256=sha(q['source']),raw_sha256=sha(q['raw']),normal='full_domain_input_risk',native_pixel_sha256=pix(native),tasks=[t]))
save(O/'plan.json',out)
for script,args in [('spacing_processor_0043.py',[MODEL]),('spacing_admit_0044.py',[])]:subprocess.run([sys.executable,str(R/'code/research'/script),*args],check=True)
binding={str(O/'inputs.json'):sha(O/'inputs.json'),str(manifest):sha(manifest),str(audit):sha(audit),str(O/'processor_plan.json'):sha(O/'processor_plan.json')}
for q in out:binding[q['raw']]=q['raw_sha256'];binding[q['source']]=q['source_sha256']
save(O/'input_binding.json',binding);save(O/'native_binding.json',dict(native_audit=str(audit),sha256=sha(audit)));deps=json.load(open(R/'reports/researcher_phase2_0044/runtime/dependencies.json'));deps={f:sha(f) for f in deps}
for n in ['shared_header_runtime_0058.py','shared_header_prepare_0058.py','shared_header_census_0058.py','shared_header_compose_0058.py','shared_header_admission_0058.py','shared_header_observe_0058.py','boundary_view_0055.py','shared_header_prepare_0057_v2.py','shared_header_census_0058.py','shared_header_0056.py','spacing_observe_0046.py','spacing_admission_0046.py']:deps[str(R/'code/research'/n)]=sha(R/'code/research'/n)
deps.update(json.load(open(O/'code_lock.json')));binding.update(json.load(open(O/'census_input_binding.json')));save(O/'input_binding.json',binding);save(O/'dependencies.json',deps);print('READY',len(out),len(rows),flush=True)
