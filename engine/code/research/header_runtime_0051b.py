"""Fixed0047 whole-domain zero-call CLI; exact byte assembly, no GT/history inputs."""
import argparse,json,os,re,sys,hashlib,time,subprocess,ast
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/research'),str(R/'code/experimenter')]
from header_group_0051b import lexical,candidate
from spacing_apply_0046 import span
from single_model_selective_v1 import hidden,HIDDEN
from PIL import Image
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def patch(data,edits):
 edits=sorted(edits);assert all(a[1]<=b[0] for a,b in zip(edits,edits[1:])),'Overlapping byte spans'
 for s,e,v in reversed(edits):data=data[:s]+v+data[e:]
 return data

def raw_spans(data,raw):
 """Bind direct blocks[i].content string/null tokens; reject duplicate/nested keys."""
 text=data.decode('utf-8');decoder=json.JSONDecoder();found={}
 def ws(pos):
  while pos<len(text) and text[pos] in ' \t\r\n':pos+=1
  return pos
 def value(pos,path):
  pos=ws(pos);start=pos
  if text[pos]=='{':
   obj={};pos=ws(pos+1)
   if text[pos]=='}':return obj,pos+1
   while True:
    key,end=decoder.raw_decode(text,pos)
    assert isinstance(key,str) and key not in obj,'Duplicate or invalid raw key'
    pos=ws(end);assert text[pos]==':','Invalid raw object'
    begin=ws(pos+1);v,pos=value(begin,path+(key,));obj[key]=v
    if key=='content':
     assert len(path)==2 and path[0]=='blocks' and isinstance(path[1],int),'Nested or extra content ambiguity'
     assert v is None or isinstance(v,str),'Unsupported raw content type'
     found[path[1]]=(begin,pos,v)
    pos=ws(pos)
    if text[pos]=='}':return obj,pos+1
    assert text[pos]==',','Invalid raw object separator';pos=ws(pos+1)
  if text[pos]=='[':
   items=[];pos=ws(pos+1)
   if text[pos]==']':return items,pos+1
   while True:
    v,pos=value(pos,path+(len(items),));items.append(v);pos=ws(pos)
    if text[pos]==']':return items,pos+1
    assert text[pos]==',','Invalid raw array separator';pos=ws(pos+1)
  return decoder.raw_decode(text,pos)
 parsed,end=value(0,());assert ws(end)==len(text) and parsed==raw,'Raw input binding mismatch'
 expected={i for i,b in enumerate(raw['blocks']) if 'content' in b}
 assert set(found)==expected,'Raw content owner ambiguity'
 result={}
 for i,(start,end,v) in found.items():
  assert v==raw['blocks'][i]['content'],'Raw owner token mismatch'
  result[i]=(len(text[:start].encode('utf-8')),len(text[:end].encode('utf-8')))
 return result

def dependencies():
 todo=[Path(__file__)];seen=set();dirs=[R/'code/research',R/'code/experimenter',R/'code/runtime']
 while todo:
  f=todo.pop().resolve()
  if f in seen:continue
  seen.add(f)
  for n in ast.walk(ast.parse(f.read_text())):
   mods=[n.module] if isinstance(n,ast.ImportFrom) and n.module else [x.name for x in n.names] if isinstance(n,ast.Import) else []
   for m in mods:
    for d in dirs:
     p=d/(m.split('.')[0]+'.py')
     if p.exists():todo.append(p)
 return {str(p):sha(p) for p in sorted(seen)}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--manifest',required=True);ap.add_argument('--out',required=True);ap.add_argument('--isolated',action='store_true',help=argparse.SUPPRESS);a=ap.parse_args()
 if not a.isolated:
  subprocess.run(hidden(['unshare','--net',sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--isolated']),check=True);return
 assert all(Path(p).stat().st_size==0 for p in HIDDEN),'GT not hidden'
 assert os.readlink('/proc/self/ns/net')!=os.readlink('/proc/1/ns/net'),'Network namespace not isolated'
 start=time.monotonic();src=Path(a.inputs).resolve();out=Path(a.out).resolve();assert not out.exists();pages=json.load(open(a.manifest));assert len(pages)==1651 and len({p['id'] for p in pages})==1651
 out.mkdir(parents=True);pred=out/'predictions'
 for sub in ['raw','markdown']:(pred/sub).mkdir(parents=True)
 records=[];bindings={};total=0;changed_pages=[]
 for pi,p in enumerate(pages):
  rp=src/'raw'/(p['id']+'.json');mp=src/'markdown'/(p['id']+'.md');rb=rp.read_bytes();md=mp.read_bytes();raw=json.loads(rb);redits=[];medits=[];seen=set();rmap=None
  bindings[str(rp)]=hashlib.sha256(rb).hexdigest();bindings[str(mp)]=hashlib.sha256(md).hexdigest()
  for owner,b in enumerate(raw['blocks']):
   if b['type']!='table':continue
   total+=1;old=b['content'];lex=lexical(old);d=dict(accepted=False,reason='no_lexical_candidate',lexical=0);new=old;sourcehash=None
   if lex:
    sourcehash=sha(p['image']);im=Image.open(p['image']).convert('RGB');w,h=im.size;im=im.crop(tuple(v*s for v,s in zip(b['bbox'],[w,h,w,h]))).rotate(b.get('angle',0),expand=True);new,d=candidate(im,old)
   apply=new!=old and d['accepted'];row=dict(manifest_index=pi,owner=owner,decision=d,applied=False,source_sha256=sourcehash,before_sha256=hashlib.sha256(old.encode()).hexdigest(),after_sha256=hashlib.sha256(new.encode()).hexdigest())
   if apply:
    assert owner not in seen,'Duplicate owner';seen.add(owner)
    try:
     if rmap is None:rmap=raw_spans(rb,raw)
     s,e,v=span(md,old,new);rs,re_=rmap[owner]
     assert not any(s<z[1] and e>z[0] for z in medits),'Overlapping Markdown owners'
     assert not any(rs<z[1] and re_>z[0] for z in redits),'Overlapping raw owners'
    except (AssertionError,KeyError) as error:row['decision']=dict(accepted=False,reason='byte_binding_ambiguous',detail=str(error))
    else:
     medits.append((s,e,v));redits.append((rs,re_,json.dumps(new,ensure_ascii=b'\\u' in rb[rs:re_]).encode()));row['applied']=True;row['markdown_span']=[s,e];row['raw_span']=[rs,re_]
   records.append(row)
  nb=patch(rb,redits);nm=patch(md,medits)
  if redits:changed_pages.append(pi)
  for sub,f,data,original in [('raw',rp,nb,rb),('markdown',mp,nm,md)]:
   target=pred/sub/f.name
   if data==original:os.link(f,target)
   else:target.write_bytes(data)
 deps=dependencies();receipt=dict(inputs=str(src),manifest=str(Path(a.manifest).resolve()),manifest_sha256=sha(a.manifest),pages=len(pages),tables=total,lexical_owners=sum(r['decision'].get('lexical',0)>0 for r in records),changed_owners=sum(r['applied'] for r in records),changed_pages=changed_pages,HTTP=0,GT_hidden=True,network_disabled=True,wall_seconds=time.monotonic()-start,records=records)
 for name,obj in [('receipt',receipt),('input_binding',bindings),('dependencies',deps)]: (out/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in receipt.items() if k!='records'},ensure_ascii=False))
if __name__=='__main__':main()
