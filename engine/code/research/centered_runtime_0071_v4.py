"""Source-band grouping: current input only, zero HTTP, GT hidden CLI."""
import datetime
import argparse,ast,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'code/research'),str(ROOT/'code/experimenter')]
from phase2_array_label_runtime_v1 import block_spans
from centered_record_0071_v2 import transform as source_transform
from connective_span_0069 import paragraph_span
from repeated_runtime_0048b import patch
from single_model_selective_v1 import hidden,HIDDEN

class LazyImage:
 def __init__(self,path):self.path=path;self.loaded=None
 def get(self):
  if self.loaded is None:
   from PIL import Image
   self.loaded=Image.open(self.path).convert('RGB')
  return self.loaded
 @property
 def size(self):return self.get().size
 def convert(self,*args,**kwargs):return self.get().convert(*args,**kwargs)
 def close(self):
  if self.loaded is not None:self.loaded.close()

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def transform(rb,md,image):
 raw=json.loads(rb);red=[];med=[];records=[]
 try:mapping=block_spans(rb,raw)
 except (AssertionError,ValueError,KeyError,TypeError):return rb,md,[dict(applied=False,reason='invalid_raw_binding')]
 for i,b in enumerate(raw['blocks']):
  if b.get('type')!='table':continue
  try:c,reason=source_transform(image,b)
  except (AssertionError,ValueError,TypeError,KeyError,IndexError):c,reason=None,'invalid_geometry_or_content'
  row=dict(owner=i,reason=reason,applied=False);records.append(row)
  if c is None:continue
  try:
   assert sum(x.get('content')==b['content'] for x in raw['blocks'])==1
   s,e,v=paragraph_span(md,b['content'],c['html']);assert not any(s<y and e>x for x,y,_ in med)
   rs,re=mapping[i];replacement=json.dumps(dict(b,content=c['html']),ensure_ascii=False).encode()
  except (AssertionError,ValueError,KeyError):row['reason']='ambiguous_owner_binding';continue
  red.append((rs,re,replacement));med.append((s,e,v));row.update(applied=True,proof=c['proof'])
 return patch(rb,red),patch(md,med),records

def dependencies():
 pending=[Path(__file__)];seen=set();dirs=[ROOT/'scripts',ROOT/'code/research',ROOT/'code/experimenter',ROOT/'code/runtime']
 while pending:
  p=pending.pop().resolve()
  if p in seen:continue
  seen.add(p)
  for n in ast.walk(ast.parse(p.read_text())):
   mods=[n.module] if isinstance(n,ast.ImportFrom) and n.module else [a.name for a in n.names] if isinstance(n,ast.Import) else []
   for m in mods:
    for d in dirs:
     f=d/(m.split('.')[0]+'.py')
     if f.exists():pending.append(f)
 return {str(p):sha(p) for p in sorted(seen)}

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for k in ['inputs','pages','out']:ap.add_argument('--'+k,required=True)
 ap.add_argument('--budget',type=int,default=8);ap.add_argument('--permit');ap.add_argument('--isolated',action='store_true');a=ap.parse_args()
 if not a.isolated:
  subprocess.run(hidden(['unshare','--net',sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--isolated']),check=True);return
 assert all(Path(p).stat().st_size==0 for p in HIDDEN)
 assert os.readlink('/proc/self/ns/net')!=os.readlink('/proc/1/ns/net')
 from PIL import Image
 source,pages,out=map(lambda p:Path(p).resolve(),[a.inputs,a.pages,a.out]);assert source.is_relative_to(ROOT) and out.is_relative_to(ROOT) and not out.exists()
 manifest=json.loads(pages.read_text());assert len(manifest)==len({p['id'] for p in manifest})==1651
 assert 0<=a.budget<=8
 began=time.monotonic();deps=dependencies();locked={str(pages):sha(pages)}
 for p in manifest:
  for sub,ext in [('raw','.json'),('markdown','.md')]:
   f=source/sub/(p['id']+ext);locked[str(f)]=sha(f)
  locked[p['image']]=sha(p['image'])
 request=dict(inputs=str(source),manifest_sha256=sha(pages),dependencies=deps,input_binding_sha256=hashlib.sha256(json.dumps(locked,sort_keys=True).encode()).hexdigest(),budget=a.budget,HTTP=0)
 now=datetime.datetime.now(datetime.timezone.utc)
 if a.permit:
  permit=json.load(open(a.permit));assert permit['approved'] is True and permit['approved_by']=='RSI' and permit['run_binding']==request
  assert datetime.datetime.fromisoformat(permit['not_before'])<=now<datetime.datetime.fromisoformat(permit['expires_at'])
 else:assert now<datetime.datetime.fromisoformat(json.load(open(ROOT/'rsi_resource_directive.json'))['drain_by'])
 for sub in ['raw','markdown']:(out/'predictions'/sub).mkdir(parents=True)
 records=[];bindings=dict(locked);changed=[];owners=0
 for index,p in enumerate(manifest):
  rp,mp=source/'raw'/(p['id']+'.json'),source/'markdown'/(p['id']+'.md');rb,md=rp.read_bytes(),mp.read_bytes()
  bindings[str(rp)]=hashlib.sha256(rb).hexdigest();bindings[str(mp)]=hashlib.sha256(md).hexdigest()
  assert sha(rp)==locked[str(rp)] and sha(mp)==locked[str(mp)] and sha(p['image'])==locked[p['image']]
  raw=json.loads(rb);image=None
  if any(b.get('type')=='table' for b in raw['blocks']):
   image=LazyImage(p['image']);bindings[p['image']]=sha(p['image'])
  nr,nm,decisions=transform(rb,md,image);count=sum(r['applied'] for r in decisions)
  if count>4 or owners+count>a.budget:
   nr,nm=rb,md
   for r in decisions:
    if r['applied']:r.update(applied=False,reason='page_or_global_budget')
   count=0
  owners+=count
  if image is not None:image.close()
  if count:changed.append(index)
  records.append(dict(manifest_index=index,decisions=decisions))
  for sub,path,data,old in [('raw',rp,nr,rb),('markdown',mp,nm,md)]:
   target=out/'predictions'/sub/path.name
   if data==old:os.link(path,target)
   else:target.write_bytes(data)
 assert all(sha(p)==h for p,h in deps.items())
 receipt=dict(request_binding=request,production_permit_used=bool(a.permit),inputs=str(source),pages_manifest=str(pages),pages_manifest_sha256=sha(pages),pages=1651,HTTP=0,GT_hidden=True,network_disabled=True,changed_pages=changed,changed_owners=owners,wall_seconds=time.monotonic()-began,records=records)
 for name,value in [('receipt',receipt),('input_binding',bindings),('dependencies',deps)]:(out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 print({k:v for k,v in receipt.items() if k!='records'})
if __name__=='__main__':main()
