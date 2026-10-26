"""Review-only runtime candidate. Input-only route; caller performs fresh same-MinerU request.
Never import offline reuse tables. Final accepted pure-rule composition is required after replacement.
"""
import math,hashlib
import cv2,numpy as np
from PIL import Image
from phase2_table_resolution_legal_0018 import legal

def glyph(im):
 a=np.asarray(im.convert('L'));bw=(a<180).astype('uint8');n,lab,st,c=cv2.connectedComponentsWithStats(bw,8);s=st[1:];good=s[(s[:,3]>=3)&(s[:,4]>=6)&(s[:,2]<=2*s[:,3])&(s[:,3]<.75*im.height)]
 return (float(np.percentile(good[:,3],75)) if len(good)>=12 else None),len(good)
def smart(w,h):
 H=max(28,round(h/28)*28);W=max(28,round(w/28)*28)
 if H*W>1605632:b=math.sqrt(h*w/1605632);H=math.floor(h/b/28)*28;W=math.floor(w/b/28)*28
 elif H*W<50176:b=math.sqrt(50176/(h*w));H=math.ceil(h*b/28)*28;W=math.ceil(w*b/28)*28
 return W,H

def prepare(image,block):
 if block.get('type')!='table' or block.get('angle',0)!=0:return None
 w,h=image.size;box=[round(v*(w if j%2==0 else h)) for j,v in enumerate(block['bbox'])];cw,ch=box[2]-box[0],box[3]-box[1]
 if min(cw,ch)<28 or cw*ch>400000 or max(cw,ch)/min(cw,ch)>45:return None
 crop=image.convert('RGB').crop(box);g,n=glyph(crop);pw,ph=smart(cw,ch);eff=None if g is None else g*ph/ch
 if not(g is not None and g>=4 and eff<16 and n>=12 and pw*ph<1000000):return None
 scale=min(2.5,max(1.25,18/eff));view=crop.resize((round(cw*scale),round(ch*scale)),Image.Resampling.LANCZOS)
 return dict(native=crop,view=view,box=box,scale=scale,prompt='\nTable Recognition:',completion_reserve=4096,context_limit=8192)

def admit(native_receipt,candidate_receipt,native_HTTP_exact_bound):
 return bool(native_HTTP_exact_bound and native_receipt['pixel_values_sha256']!=candidate_receipt['pixel_values_sha256'] and candidate_receipt['prompt_tokens']+4096<=8192 and candidate_receipt['processed_size'][1]>native_receipt['processed_size'][1])

def choose(old_content,new_content,raw_answer,finish):
 ok,reason=legal(new_content,raw_answer,finish)
 return (new_content if ok else old_content),dict(accepted=ok,reason=reason)
