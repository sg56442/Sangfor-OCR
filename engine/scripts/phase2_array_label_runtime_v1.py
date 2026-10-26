"""Source-bound single-row label split; preserve all unrelated raw/Markdown bytes."""
import argparse,ast,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from phase2_array_prose_label_v1 import candidate,transform as source_transform
from phase2_mixed_prose_runtime_v1 import owner_tokens
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/research'),str(ROOT/'code/experimenter')]
from repeated_runtime_0048b import patch
from spacing_apply_0046 import span
from single_model_selective_v1 import hidden,HIDDEN

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def block_spans(rb,raw):
 # This validates all duplicate keys and direct content/type ownership before
 # collecting complete object spans. No regex locates a JSON owner.
 owner_tokens(rb,raw);s=rb.decode();dec=json.JSONDecoder()
 def ws(i):
  while i<len(s) and s[i].isspace():i+=1
  return i
 i=ws(0);assert s[i]=='{';i=ws(i+1);array_start=None
 while s[i]!='}':
  key,j=dec.raw_decode(s,i);i=ws(j);assert s[i]==':';i=ws(i+1)
  if key=='blocks':array_start=i
  _,i=dec.raw_decode(s,i);i=ws(i)
  if s[i]=='}':break
  assert s[i]==',';i=ws(i+1)
 assert array_start is not None and s[array_start]=='[';i=ws(array_start+1);result={};index=0
 while s[i]!=']':
  begin=i;obj,i=dec.raw_decode(s,i);assert obj==raw['blocks'][index] and isinstance(obj,dict)
  result[index]=(len(s[:begin].encode()),len(s[:i].encode()));index+=1;i=ws(i)
  if s[i]==']':break
  assert s[i]==',';i=ws(i+1)
 assert index==len(raw['blocks']);return result

def transform(rb,md,image):
 raw=json.loads(rb);redits=[];medits=[];records=[];mapping=None
 for owner,b in enumerate(raw['blocks']):
  if b['type']!='equation' or candidate(b.get('content') or '') is None:continue
  parts,decision=source_transform(image,b);row=dict(owner=owner,applied=False,decision=decision)
  if decision['applied']:
   try:
    if mapping is None:mapping=block_spans(rb,raw)
    new=parts[0]['content']+'\n\n'+parts[1]['content'];start,end,text=span(md,b['content'],new);rs,re_=mapping[owner]
    assert not any(start<e and end>s for s,e,_ in medits),'Overlapping Markdown owners'
    assert not any(rs<e and re_>s for s,e,_ in redits),'Overlapping raw owners'
   except (AssertionError,KeyError,ValueError) as error:row.update(reason='ambiguous_owner_binding',detail=str(error))
   else:
    separator=b',\r\n' if b'\r\n' in rb else b',\n'
    replace=separator.join(json.dumps(p,ensure_ascii=b'\\u' in rb[rs:re_]).encode() for p in parts)
    redits.append((rs,re_,replace));medits.append((start,end,text));row.update(applied=True,new_blocks=parts,raw_span=[rs,re_],markdown_span=[start,end])
  records.append(row)
 return patch(rb,redits),patch(md,medits),records

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
 ap.add_argument('--isolated',action='store_true');a=ap.parse_args()
 if not a.isolated:
  subprocess.run(hidden(['unshare','--net',sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--isolated']),check=True);return
 assert all(Path(p).stat().st_size==0 for p in HIDDEN)
 assert os.readlink('/proc/self/ns/net')!=os.readlink('/proc/1/ns/net')
 from PIL import Image
 source,pages,out=map(lambda p:Path(p).resolve(),[a.inputs,a.pages,a.out]);assert source.is_relative_to(ROOT) and out.is_relative_to(ROOT) and not out.exists()
 manifest=json.loads(pages.read_text());assert len(manifest)==len({p['id'] for p in manifest})==1651
 for sub in ['raw','markdown']:(out/'predictions'/sub).mkdir(parents=True)
 began=time.monotonic();records=[];bindings={};changed=[];owners=0
 for index,p in enumerate(manifest):
  rp,mp=source/'raw'/(p['id']+'.json'),source/'markdown'/(p['id']+'.md');rb,md=rp.read_bytes(),mp.read_bytes()
  bindings[str(rp)]=hashlib.sha256(rb).hexdigest();bindings[str(mp)]=hashlib.sha256(md).hexdigest()
  raw=json.loads(rb);image=None
  if any(b['type']=='equation' and candidate(b.get('content') or '') is not None for b in raw['blocks']):
   image=Image.open(p['image']).convert('RGB');bindings[p['image']]=sha(p['image'])
  nr,nm,decisions=transform(rb,md,image);count=sum(r['applied'] for r in decisions);owners+=count
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
