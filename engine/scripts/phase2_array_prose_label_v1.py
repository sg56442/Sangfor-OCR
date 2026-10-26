"""Source-only census of one-row prose-label arrays; zero document inference."""
import argparse,json,re,sys,hashlib,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/experimenter')]
from single_model_selective_v1 import hidden,HIDDEN
from phase2_formula_label_v1 import split as source_split

def candidate(content):
 match=re.fullmatch(r'\s*\\\[\s*\\begin\s*\{array\}\s*\{\s*([clr])\s*([clr])\s*\}(.*?)\\end\s*\{array\}\s*\\\]\s*',content,re.S)
 if not match:return None
 body=match[3];depth=0;environments=[];splits=[];i=0
 while i<len(body):
  env=re.match(r'\\(begin|end)\s*\{([A-Za-z*]+)\}',body[i:])
  if env:
   if env[1]=='begin':environments.append(env[2])
   elif not environments or environments.pop()!=env[2]:return None
   i+=len(env[0]);continue
  if body[i]=='\\':
   if body[i:i+2]=='\\\\' and depth==0 and not environments:return None
   token=re.match(r'\\[A-Za-z]+|\\.',body[i:]);i+=len(token[0]) if token else 1;continue
  if body[i]=='{':depth+=1
  elif body[i]=='}':
   depth-=1
   if depth<0:return None
  elif body[i]=='&' and depth==0 and not environments:splits.append(i)
  i+=1
 if depth or environments or len(splits)!=1:return None
 left,right=body[:splits[0]].strip(),body[splits[0]+1:].strip()
 label=re.fullmatch(r'\\(?:text|mbox)\s*\{([A-Za-z]+(?:[ -][A-Za-z]+)+)\}',left)
 if not label or not right:return None
 # Keep the complete mathematics as a separate display. Only a plain layout
 # array enclosing a natural-language label and one complete math cell moves.
 return r'\[\text{'+label[1]+r'}\quad '+right+r'\]'

def transform(image,block):
 if block.get('type')!='equation' or block.get('angle',0)!=0:return [block],dict(applied=False,reason='ineligible_owner')
 proposal=candidate(block.get('content') or '')
 if proposal is None:return [block],dict(applied=False,reason='not_plain_single_row_label_array')
 probe=dict(block,content=proposal);blocks,trace=source_split(image,probe)
 if not trace['applied']:return [block],trace
 trace.update(original_array=block['content'],array_layout_only_removed=True)
 return blocks,trace

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--inputs',required=True);ap.add_argument('--pages',required=True);ap.add_argument('--out',required=True);ap.add_argument('--hidden',action='store_true');a=ap.parse_args()
 if not a.hidden:
  subprocess.run(hidden(['unshare','--net',sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--hidden']),check=True);return
 assert all(Path(p).stat().st_size==0 for p in HIDDEN)
 from PIL import Image
 base,out=Path(a.inputs).resolve(),Path(a.out).resolve();assert base.is_relative_to(ROOT) and out.is_relative_to(ROOT) and not out.exists();out.mkdir()
 pages=json.loads(Path(a.pages).read_text());assert len(pages)==1651
 rows=[];bindings={};start=time.monotonic()
 for p in pages:
  f=base/'raw'/(p['id']+'.json');bindings[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest();raw=json.loads(f.read_text());im=None
  for i,b in enumerate(raw['blocks']):
   if b['type']!='equation' or candidate(b.get('content') or '') is None:continue
   if im is None:im=Image.open(p['image']).convert('RGB')
   new,trace=transform(im,b);r=dict(page=p['id'],source=p['image'],owner=i,before=b,after=new,trace=trace);rows.append(r)
   box=[round(v*(im.width if k%2==0 else im.height)) for k,v in enumerate(b['bbox'])]
   im.crop((max(0,box[0]-35),max(0,box[1]-35),min(im.width,box[2]+35),min(im.height,box[3]+35))).save(out/('source_'+str(len(rows))+'.png'))
 result=dict(status='CENSUS_ONLY',HTTP=0,pages=1651,candidates=len(rows),accepted=sum(r['trace']['applied'] for r in rows),rows=rows,bindings=bindings,wall_seconds=time.monotonic()-start,GT_hidden=True,network_disabled=True)
 (out/'census.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print({k:v for k,v in result.items() if k not in ['rows','bindings']})
if __name__=='__main__':main()
