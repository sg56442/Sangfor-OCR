import json,sys,hashlib,time,subprocess,os
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/research'),str(R/'code/experimenter')]
from single_model_selective_v1 import hidden
if '--isolated' not in sys.argv:
 subprocess.run(hidden(['unshare','--net',sys.executable,__file__,'--isolated']),check=True);raise SystemExit
from shared_header_0056 import geometry
from boundary_view_0055 import detect,expand
from spacing_gate_0042 import grid
from PIL import Image
O=Path(os.environ['SPACING_OUT']);cfg=json.load(open(O/'inputs.json'));src=Path(cfg['inputs']);pages=json.load(open(cfg['manifest']));start=time.monotonic();rows=[];tables=0;pref=0;binding={}
for p in pages:
 rp=src/'raw'/(p['id']+'.json');raw=json.load(open(rp));binding[str(rp)]=hashlib.sha256(rp.read_bytes()).hexdigest();im=None
 for j,b in enumerate(raw['blocks']):
  if b['type']!='table':continue
  tables+=1;g=grid(b.get('content') or '')
  if not g or g['width']<2 or b.get('angle',0):continue
  bb=b['bbox'];width=bb[2]-bb[0];caps=[]
  for k,c in enumerate(raw['blocks']):
   if c['type']!='table_caption' or not isinstance(c.get('content'),str) or not c['content'].strip():continue
   cb=c['bbox'];height=cb[3]-cb[1]
   if cb[1]<bb[1] and abs(cb[3]-bb[1])<=height and cb[0]>=bb[0]-.005 and cb[2]<bb[2] and cb[2]-cb[0]<width*.8:caps.append((k,c))
  if not caps:continue
  pref+=1
  if im is None:im=Image.open(p['image']).convert('RGB')
  a,box,hits=detect(im,bb);top=[q for q in hits if 'top' in q['sides']]
  if not top:continue
  _,expanded=expand(a,box,hits)
  for k,c in caps:
   geo=geometry(im,b,c,expanded);text=c['content'];unique=sum(z.get('content')==text for z in raw['blocks'])==1
   neighbors=[x for x,z in enumerate(raw['blocks']) if x!=j and z['type']=='table' and z['bbox'][0]<=(c['bbox'][0]+c['bbox'][2])/2<=z['bbox'][2] and z['bbox'][1]<=(c['bbox'][1]+c['bbox'][3])/2<=z['bbox'][3]]
   accepted=geo['accepted'] and unique and not neighbors;priority=hashlib.sha256(json.dumps(dict(content=b['content'],bbox=bb,angle=b.get('angle',0)),sort_keys=True,ensure_ascii=False).encode()).hexdigest();rows.append(dict(source=p['image'],source_sha256=hashlib.sha256(Path(p['image']).read_bytes()).hexdigest(),raw=str(rp),owner=j,caption_owner=k,priority=priority,geometry=geo,expanded=expanded,unique=unique,other_table_owners=neighbors,input_risk=accepted))
rows.sort(key=lambda q:q['priority']);out=dict(inputs=str(src),pages=len(pages),tables=tables,partial_topcaption_prefilter=pref,topcrossing_candidates=len(rows),risk_owners=sum(q['input_risk'] for q in rows),risk_sources=len({q['source'] for q in rows if q['input_risk']}),rows=rows,seconds=time.monotonic()-start,HTTP=0,scope='input-only risk, notresponse admission; noGT/history/source-id predicates',input_binding_sha256=hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest());(O/'census.json').write_text(json.dumps(out,indent=2));(O/'census_input_binding.json').write_text(json.dumps(binding,indent=2));print({k:v for k,v in out.items() if k!='rows'})
