"""Image-only candidate geometry using caller-supplied current native blocks."""
import pathlib,json,hashlib,numpy as np
from PIL import Image

def prepare(image_path,blocks,out):
 out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=False);im=Image.open(image_path).convert('RGB');pw,ph=im.size;proposals=[];requests=[]
 for index,b in enumerate(blocks):
  if b['type']!='equation' or b.get('angle') not in (0,None):continue
  x0,y0,x1,y1=b['bbox'];crop=im.crop((x0*pw,y0*ph,x1*pw,y1*ph));w,h=crop.size
  if min(w,h)<=0 or w/h<2.8:continue
  ink=np.asarray(crop.convert('L'))<170;edges=np.diff(np.r_[False,ink.mean(0)<.01,False].astype(int));gaps=[(int(s),int(e)) for s,e in zip(np.where(edges==1)[0],np.where(edges==-1)[0]) if s>.2*w and e<.8*w and e-s>=max(12,.05*w)]
  if not gaps:continue
  s,e=max(gaps,key=lambda z:z[1]-z[0]);cut=(s+e)//2;content=b.get('content') or '';trigger=content.count('=')>=2 and ('\\quad' in content or '\\;' in content) and not any(t in content for t in ['\\begin','\\cases','\\matrix']);pi=len(proposals);proposals.append(dict(proposal_id=pi,index=index,bbox=b['bbox'],page_size=[pw,ph],size=[w,h],cut=cut,gap_width=e-s,native_content=content,triggered=trigger,normal_control=not trigger));bound=x0+(x1-x0)*cut/w
  for kind,box,bb in [('native',(0,0,w,h),b['bbox']),('left',(0,0,cut,h),[x0,y0,bound,y1]),('right',(cut,0,w,h),[bound,y0,x1,y1])]:
   candidate=crop.crop(box);path=out/f'p{pi}_{kind}.png';candidate.save(path);a,bottom,c,top=bb;requests.append(dict(proposal=pi,kind=kind,image=str(path.resolve()),task='equation',bbox=bb,size=candidate.size,affine_candidate_to_page=[(c-a)*pw/candidate.width,0,a*pw,0,(top-bottom)*ph/candidate.height,bottom*ph],encoded_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 (out/'proposals.json').write_text(json.dumps(proposals,indent=2));(out/'requests.json').write_text(json.dumps(requests,indent=2));return proposals,requests
