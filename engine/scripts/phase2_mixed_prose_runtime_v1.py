"""Zero-call current-input mixed-statement serialization with exact owner-token edits."""
import argparse,ast,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from phase2_mixed_prose_scope_v4 import convert
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/research'),str(ROOT/'code/experimenter')]
from repeated_runtime_0048b import patch
from spacing_apply_0046 import span
from single_model_selective_v1 import hidden,HIDDEN

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def owner_tokens(data,raw):
 text=data.decode('utf-8');decoder=json.JSONDecoder();found={}
 def ws(pos):
  while pos<len(text) and text[pos].isspace():pos+=1
  return pos
 def value(pos,path):
  pos=ws(pos)
  if text[pos]=='{':
   obj={};pos=ws(pos+1)
   if text[pos]=='}':return obj,pos+1
   while True:
    key,end=decoder.raw_decode(text,pos);assert isinstance(key,str) and key not in obj,'Duplicate JSON key'
    pos=ws(end);assert text[pos]==':'
    start=ws(pos+1);item,pos=value(start,path+(key,));obj[key]=item
    if key in ('type','content') and len(path)==2 and path[0]=='blocks' and isinstance(path[1],int):
     assert isinstance(item,str) if key=='type' else item is None or isinstance(item,str)
     found[(path[1],key)]=(len(text[:start].encode()),len(text[:pos].encode()))
    if key=='content':assert len(path)==2 and path[0]=='blocks' and isinstance(path[1],int),'Nested content ambiguity'
    pos=ws(pos)
    if text[pos]=='}':return obj,pos+1
    assert text[pos]==',';pos=ws(pos+1)
  if text[pos]=='[':
   items=[];pos=ws(pos+1)
   if text[pos]==']':return items,pos+1
   while True:
    item,pos=value(pos,path+(len(items),));items.append(item);pos=ws(pos)
    if text[pos]==']':return items,pos+1
    assert text[pos]==',';pos=ws(pos+1)
  return decoder.raw_decode(text,pos)
 parsed,end=value(0,());assert ws(end)==len(text) and parsed==raw
 expected={(i,key) for i,b in enumerate(raw['blocks']) for key in ('type','content') if key in b}
 assert found.keys()==expected
 return found

def transform(rb,md):
 raw=json.loads(rb);redits=[];medits=[];records=[];bindings=None
 for i,b in enumerate(raw['blocks']):
  if b['type']!='equation' or not b.get('content'):continue
  new,reason=convert(b['content']);record=dict(owner=i,proposed=new is not None,applied=False,reason=reason)
  if new is not None:
   try:
    if bindings is None:bindings=owner_tokens(rb,raw)
    s,e,v=span(md,b['content'],new);rs,re_=bindings[(i,'content')];ts,te=bindings[(i,'type')]
    assert not any(s<end and e>start for start,end,_ in medits),'Overlapping Markdown owners'
    assert not any(rs<end and re_>start or ts<end and te>start for start,end,_ in redits),'Overlapping raw owners'
   except (AssertionError,KeyError,ValueError) as error:record.update(reason='ambiguous_byte_binding',detail=str(error))
   else:
    redits.extend([(rs,re_,json.dumps(new,ensure_ascii=b'\\u' in rb[rs:re_]).encode()),(ts,te,b'"text"')]);medits.append((s,e,v))
    record.update(applied=True,before_sha256=hashlib.sha256(b['content'].encode()).hexdigest(),after_sha256=hashlib.sha256(new.encode()).hexdigest(),raw_content_span=[rs,re_],raw_type_span=[ts,te],markdown_span=[s,e])
  records.append(record)
 return patch(rb,redits),patch(md,medits),records

def dependencies():
 pending=[Path(__file__)];seen=set();dirs=[ROOT/'scripts',ROOT/'code/research',ROOT/'code/experimenter',ROOT/'code/runtime']
 while pending:
  path=pending.pop().resolve()
  if path in seen:continue
  seen.add(path)
  for node in ast.walk(ast.parse(path.read_text())):
   mods=[node.module] if isinstance(node,ast.ImportFrom) and node.module else [n.name for n in node.names] if isinstance(node,ast.Import) else []
   for mod in mods:
    for folder in dirs:
     p=folder/(mod.split('.')[0]+'.py')
     if p.exists():pending.append(p)
 return {str(p):sha(p) for p in sorted(seen)}

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for key in ['inputs','pages','out']:ap.add_argument('--'+key,required=True)
 ap.add_argument('--isolated',action='store_true');a=ap.parse_args()
 if not a.isolated:
  subprocess.run(hidden(['unshare','--net',sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--isolated']),check=True);return
 assert all(Path(p).stat().st_size==0 for p in HIDDEN)
 assert os.readlink('/proc/self/ns/net')!=os.readlink('/proc/1/ns/net')
 source,pages,out=map(lambda p:Path(p).resolve(),[a.inputs,a.pages,a.out]);assert source.is_relative_to(ROOT) and out.is_relative_to(ROOT) and not out.exists()
 manifest=json.loads(pages.read_text());assert len(manifest)==len({p['id'] for p in manifest})==1651
 for sub in ['raw','markdown']:(out/'predictions'/sub).mkdir(parents=True)
 records=[];bindings={};changed=[];owners=0;began=time.monotonic()
 for index,p in enumerate(manifest):
  rp,mp=source/'raw'/(p['id']+'.json'),source/'markdown'/(p['id']+'.md');rb,md=rp.read_bytes(),mp.read_bytes()
  bindings[str(rp)]=hashlib.sha256(rb).hexdigest();bindings[str(mp)]=hashlib.sha256(md).hexdigest()
  nr,nm,decisions=transform(rb,md);count=sum(q['applied'] for q in decisions);owners+=count
  if count:changed.append(index)
  records.append(dict(manifest_index=index,decisions=decisions))
  for sub,path,data,old in [('raw',rp,nr,rb),('markdown',mp,nm,md)]:
   target=out/'predictions'/sub/path.name
   if data==old:os.link(path,target)
   else:target.write_bytes(data)
 receipt=dict(inputs=str(source),pages_manifest=str(pages),pages_manifest_sha256=sha(pages),pages=1651,HTTP=0,GT_hidden=True,network_disabled=True,changed_pages=changed,changed_owners=owners,wall_seconds=time.monotonic()-began,records=records)
 for name,value in [('receipt',receipt),('input_binding',bindings),('dependencies',dependencies())]:(out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 print({k:v for k,v in receipt.items() if k!='records'})
if __name__=='__main__':main()
