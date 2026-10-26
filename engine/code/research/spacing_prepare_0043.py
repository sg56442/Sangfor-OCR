import json,sys,hashlib,io,os
from pathlib import Path
import numpy as np,cv2
from PIL import Image
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/experimenter'),str(R/'code/research')]
from finite_request_identity_0101_v1 import helper,pix,key,params
from mineru_vl_utils.structs import ContentBlock
from table_partition_0038 import bands
O=Path(os.environ['SPACING_OUT']);C=json.load(open(O/'census.json'))['rows'];M=[]
for q in C:
 rp=R/q['raw'];M.append(dict(raw=str(rp),source=q['image'],source_sha256=hashlib.sha256(Path(q['image']).read_bytes()).hexdigest(),tables=[dict(index=q['owner'])]))
hh=helper();rows=[]
# Contract separately frozen before any new response.
for i in range(len(M)):
 q=M[i];rp=R/q['raw'];raw=json.load(open(rp));owner=q['tables'][0]['index'];b=raw['blocks'][owner];im=Image.open(q['source']).convert('RGB');w,h=im.size;crop=im.crop(tuple(v*s for v,s in zip(b['bbox'],[w,h,w,h]))).rotate(b.get('angle',0),expand=True);crop.save(O/f'source_{i}.png');a=np.array(crop);mask=(cv2.cvtColor(a,cv2.COLOR_RGB2GRAY)<180).astype('uint8');hhorizontal=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((1,max(30,crop.width//2)),np.uint8));vertical=cv2.morphologyEx(cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((7,1),np.uint8)),cv2.MORPH_OPEN,np.ones((max(30,crop.height//2),1),np.uint8));ink=mask & ~(hhorizontal|vertical);nn,ll,stats,_=cv2.connectedComponentsWithStats(ink,8);keep=np.zeros(nn,dtype='uint8');keep[1:]=((stats[1:,cv2.CC_STAT_AREA]>=6)&(stats[1:,cv2.CC_STAT_HEIGHT]>=3)&(stats[1:,cv2.CC_STAT_WIDTH]>=2));ink=keep[ll];tb=bands(ink.sum(1)>max(1,crop.width*.001));height=float(np.median([e-s for s,e in tb if e-s>=3]));pad=max(4,min(24,int(np.ceil(height*.75))));seams=[(s+e)//2 for s,e in bands(ink.sum(1)<=max(1,crop.width*.001)) if e-s>=3 and s>3 and e<crop.height-3];
 if not seams:continue
 chunks=[];mapping=[];start=0;offset=0
 for y in seams+[crop.height]:
  chunks.append(a[start:y]);mapping.append([start,y,offset,offset+y-start]);offset+=y-start
  if y<crop.height:chunks.append(np.full((pad,crop.width,3),255,np.uint8));offset+=pad
  start=y
 va=np.concatenate(chunks);assert np.array_equal(np.concatenate([va[z0:z1] for _,_,z0,z1 in mapping]),a);view=Image.fromarray(va);view.save(O/f'view_{i}_0_source.png')
 native,pp,_,_=hh.prepare_for_extract(im,[ContentBlock(type='table',bbox=b['bbox'],angle=b.get('angle',0))]);n=Image.open(io.BytesIO(native[0]));n.save(O/f'native_{i}.png');ims,ps,_,_=hh.prepare_for_extract(view,[ContentBlock(type='table',bbox=[0.,0.,1.,1.],angle=0)]);v=Image.open(io.BytesIO(ims[0]));
 v.save(O/f'view_{i}_0_prepared.png');(O/f'view_{i}_0.bin').write_bytes(ims[0]);t=dict(view=0,prompt=ps[0],identity=key(v.size,pix(v),'table'),pixel_sha256=pix(v),encoded_sha256=hashlib.sha256(ims[0]).hexdigest(),parameters=params('table'))
 rows.append(dict(index=i,source=q['source'],source_sha256=q['source_sha256'],raw=str(rp),raw_sha256=hashlib.sha256(rp.read_bytes()).hexdigest(),owner=owner,normal=None,native_pixel_sha256=pix(n),geometry=dict(seams=seams,pad=pad,median_band_height=height,mapping=mapping,reversible_pixel_exact=True,original_size=crop.size,view_size=view.size),tasks=[t]))
(O/'plan.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print([(q['index'],q['geometry']['pad'],len(q['geometry']['seams']),q['geometry']['view_size']) for q in rows])
