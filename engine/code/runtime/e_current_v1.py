"""Frozen E detector applied to caller current pixels/blocks; no GT or identity features."""
import pathlib,json,hashlib,shutil,argparse,cv2,numpy as np
from PIL import Image
R=pathlib.Path(__file__).resolve().parents[2]
def prepare(native,pages,out):
 out=pathlib.Path(out).resolve();assert out.is_relative_to(R);out.mkdir(parents=True,exist_ok=False);native=pathlib.Path(native);props=[];requests=[];scanned=0;sources=[]
 for page in pages:
  pid=page['id'];rawpath=native/'raw'/f'{pid}.json';bs=json.load(open(rawpath))['blocks'];im=None
  sources.append({'page_locator':pid,'raw_sha256':hashlib.sha256(rawpath.read_bytes()).hexdigest(),'markdown_sha256':hashlib.sha256((native/'markdown'/f'{pid}.md').read_bytes()).hexdigest()})
  for i,b in enumerate(bs):
   if b['type']!='text' or b.get('angle') not in (None,0):continue
   x,y,z,t=b['bbox'];s=b.get('content') or '';area=(z-x)*(t-y)
   if area<.08 or len(s)<100:continue
   scanned+=1
   if im is None:im=Image.open(page['image']).convert('RGB')
   pw,ph=im.size;crop=im.crop((x*pw,y*ph,z*pw,t*ph));w,h=crop.size
   ink=(np.asarray(crop.convert('L'))<150).astype('uint8');lines=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(30,w//3)),np.uint8));mask=ink & (1-lines);density=mask.mean(axis=0);threshold=min(.08,float(np.percentile(density,10))+.015,float(np.median(density))*.5)
   edges=np.diff(np.r_[False,density<threshold,False].astype(int));gaps=[(int(a),int(c)) for a,c in zip(np.where(edges==1)[0],np.where(edges==-1)[0]) if a>.12*w and c<.88*w and c-a>=max(10,.018*w)];gaps=sorted(sorted(gaps,key=lambda q:-(q[1]-q[0]))[:3]);cuts=[0]+[(a+c)//2 for a,c in gaps]+[w]
   if len(cuts)<=2:continue
   pi=len(props);props.append(dict(proposal_id=pi,page=pid,index=i,bbox=b['bbox'],page_size=[pw,ph],size=[w,h],native_content=s,cuts=cuts,gaps=gaps,ink_threshold=threshold,triggered=True))
   for kind,a,c in [('native',0,w)]+[(f'col{k}',a,c) for k,(a,c) in enumerate(zip(cuts,cuts[1:]))]:
    roi=crop.crop((a,0,c,h));path=out/f'p{pi}_{kind}.png';roi.save(path);bb=[x+(z-x)*a/w,y,x+(z-x)*c/w,t];requests.append(dict(proposal=pi,kind=kind,image=str(path),task='[default]',bbox=bb,size=roi.size,affine_candidate_to_page=[(bb[2]-bb[0])*pw/roi.width,0,bb[0]*pw,0,(t-y)*ph/roi.height,y*ph],encoded_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 base=out/'baseline/predictions'
 for folder in ['raw','markdown']:(base/folder).mkdir(parents=True)
 for page in pages:
  for folder,suffix in [('raw','.json'),('markdown','.md')]:shutil.copyfile(native/folder/(page['id']+suffix),base/folder/(page['id']+suffix))
 for name,value in [('proposals',props),('requests',requests),('current_native_identity',sources),('preparation',dict(family='E_current_v1',pages=len(pages),configured=len(props),requests=len(requests),scanned_large_text_ROIs=scanned,runtime_GT=False,caller_native=str(native)))]: (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2))
 return props,requests
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--pages',required=True);p.add_argument('--out',required=True);a=p.parse_args();prepare(a.native,json.load(open(a.pages)),a.out)
