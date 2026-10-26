import os,sys,json,io,subprocess,hashlib,time
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/research'),str(R/'code/experimenter')]
from single_model_selective_v1 import hidden
if '--isolated' not in sys.argv:subprocess.run(hidden(['unshare','--net',sys.executable,__file__,'--isolated']),check=True);raise SystemExit
from finite_request_identity_0101_v1 import helper,pix,key,params,MODEL,prompts
from mineru_vl_utils.structs import ContentBlock
from spacing_state_0044 import save,sha
from column_view_0059 import measure
O=Path(os.environ['SPACING_OUT']);cfg=json.load(open(O/'inputs.json'));audit=Path(cfg['native_audit']);src=Path(cfg['inputs']);subprocess.run([sys.executable,str(R/'code/research/column_census_0060.py')],check=True);samples=[dict(**q,normal=False) for q in json.load(open(O/'census.json'))['rows'] if q['geometry']['risk']][:cfg['budget']]
hh=helper();out=[]
for i,q in enumerate(samples):
 raw=json.load(open(q['raw']));b=raw['blocks'][q['owner']];im=Image.open(q['source']).convert('RGB');crop=im.crop(q['geometry']['expanded_box']);crop.save(O/f'view_{i}_0_source.png');ni,_,_,_=hh.prepare_for_extract(im,[ContentBlock(type='table',bbox=b['bbox'],angle=b.get('angle',0))]);native=Image.open(io.BytesIO(ni[0]));native.save(O/f'native_{i}.png');vi,ps,_,_=hh.prepare_for_extract(crop,[ContentBlock(type='text',bbox=[0,0,1,1],angle=b.get('angle',0))]);v=Image.open(io.BytesIO(vi[0]));v.save(O/f'view_{i}_0_prepared.png');(O/f'view_{i}_0.bin').write_bytes(vi[0]);t=dict(view=0,kind='text',prompt=ps[0],identity=key(v.size,pix(v),'text'),pixel_sha256=pix(v),encoded_sha256=sha(O/f'view_{i}_0.bin'),parameters=params('text'));out.append(dict(**{k:v for k,v in q.items() if k not in ['source_sha256','raw_sha256']},index=i,source_sha256=sha(q['source']),raw_sha256=sha(q['raw']),native_pixel_sha256=pix(native),native_prepared_size=native.size,view_prepared_size=v.size,tasks=[t]))
save(O/'plan.json',out);subprocess.run([sys.executable,str(R/'code/research/spacing_processor_0043.py'),MODEL],check=True)
qs=json.load(open(O/'processor_plan.json'));wanted={q['native_pixel_sha256'] for q in qs};native_receipts={};text_ref=None
configured={};consumed={}
for line in audit.open():
 z=json.loads(line);k=z.get('request_sha256')
 if z.get('stage')=='configured':configured[k]=z
 elif z.get('stage')=='consumed':consumed.setdefault(k,[]).append(z)
for k,z in configured.items():
 good=[v for v in consumed.get(k,[]) if v.get('response',{}).get('model')==MODEL and len(v['response'].get('choices',[]))==1 and v['response']['choices'][0].get('finish_reason')=='stop' and isinstance(v['response'].get('usage'),dict)]
 if len(good)!=1:continue
 receipt=dict(z,consumed=good[0])
 if z['parameters']==params('text') and z['prompts']==prompts('text'):text_ref=receipt
 if z['parameters']==params('table') and z['prompts']==prompts('table'):
  for v in z.get('images',[]):
   if v['pixel_sha256'] in wanted:native_receipts[v['pixel_sha256']]=receipt
assert not qs or text_ref,'No completed native Text reference'
for q in qs:q['original_owner_native_receipt']=native_receipts[q['native_pixel_sha256']];q['native_receipt']=text_ref
save(O/'processor_plan.json',qs)
# Retain census binding and bind every raw/MD, every source and actual native audit.
bind=json.load(open(O/'input_binding.json'));pixels={}
for page in json.load(open(cfg['manifest'])):
 for sub,ext in [('raw','.json'),('markdown','.md')]:
  path=src/sub/(page['id']+ext);bind[str(path)]=sha(path)
 path=Path(page['image']);bind[str(path)]=sha(path)
 # Encoded source hash binds all source bytes; actual inference pixels bound below.
for q in qs:pixels[q['source']]=dict(source_sha256=q['source_sha256'],native_pixel_sha256=q['native_pixel_sha256'],tasks=[t['pixel_sha256'] for t in q['tasks']])
save(O/'source_pixel_binding.json',pixels)
for path in [Path(cfg['manifest']),audit,O/'inputs.json',O/'processor_plan.json',O/'source_pixel_binding.json']:
 bind[str(path)]=sha(path)
for q in qs:
 for t in q['tasks']:
  path=O/f"view_{q['index']}_{t['view']}.bin";bind[str(path)]=sha(path)
save(O/'input_binding.json',bind);save(O/'native_binding.json',dict(path=str(audit),sha256=sha(audit),consumed_verified=True));deps=json.load(open(O/'code_lock.json'));save(O/'dependencies.json',deps);print('READY',len(qs),'bindings',len(bind),flush=True)
