"""Current-input syntax/overlap census; no GT or page identity features."""
import json,re,time,argparse,hashlib
from pathlib import Path

def defects(s):
 out=[]; clean=re.sub(r'\\[{}]','',s); depth=0
 for c in clean:
  if c=='{':depth+=1
  if c=='}':depth-=1
  if depth<0:out.append('unmatched_close');break
 if depth:out.append('unbalanced_braces')
 for m in re.finditer(r'\\(?:dfrac|tfrac|frac|binom)\s*',s):
  pos=m.end()
  for _ in range(2):
   while pos<len(s) and s[pos].isspace():pos+=1
   if pos>=len(s):out.append('missing_binary_argument');break
   if s[pos]=='{':
    end=pos+1;d=1
    while end<len(s) and d:
     if s[end]=='{':d+=1
     elif s[end]=='}':d-=1
     end+=1
    if d:out.append('unterminated_binary_argument');break
    if not s[pos+1:end-1].strip():out.append('empty_binary_argument')
    pos=end
   elif s[pos]=='\\':
    mm=re.match(r'\\[A-Za-z]+|\\.',s[pos:]);pos+=len(mm.group()) if mm else 1
   else:pos+=1
 if re.findall(r'\\begin\{([^}]+)\}',s)!=re.findall(r'\\end\{([^}]+)\}',s):out.append('environment_mismatch')
 return sorted(set(out))
def proposals(bs):
 out=[]
 for i,b in enumerate(bs):
  if b['type'] not in ('equation','text') or not b.get('content'):continue
  s=b['content'];bad=defects(s);bb=b['bbox'];near=[];over=[]
  for j,c in enumerate(bs):
   if i==j or c['type'] not in ('equation','text'):continue
   cb=c['bbox'];h=min(bb[3]-bb[1],cb[3]-cb[1]);xo=max(0,min(bb[2],cb[2])-max(bb[0],cb[0]));yo=max(0,min(bb[3],cb[3])-max(bb[1],cb[1]));gap=max(0,max(bb[1],cb[1])-min(bb[3],cb[3]))
   if xo>0 and yo>h*.5:over.append(j)
   if xo>=.7*min(bb[2]-bb[0],cb[2]-cb[0]) and gap<=.6*h:near.append(j)
  if bad or (over and b['type']=='equation') or '\\binom' in s:
   out.append(dict(index=i,defects=bad,overlap=over,near=near,binom='\\binom' in s,bbox=bb,content=s))
 return out
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--raw',required=True);a.add_argument('--out',required=True);args=a.parse_args();t=time.monotonic();rows=[];n=0
 for p in sorted(Path(args.raw).glob('*.json')):
  r=json.loads(p.read_text());n+=1
  for x in proposals(r['blocks']):rows.append(dict(raw=str(p),**x))
 o=Path(args.out);o.mkdir(parents=True,exist_ok=True);(o/'census.json').write_text(json.dumps(dict(pages=n,records=rows,seconds=time.monotonic()-t,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),ensure_ascii=False,indent=2));print('pages',n,'records',len(rows))
 for x in rows:print(Path(x['raw']).stem,x['index'],x['defects'],x['overlap'],x['near'],x['content'][:160])
