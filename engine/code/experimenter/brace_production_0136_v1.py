"""Current-input brace census; conservative geometry/ownership admission. No diagnostic reads."""
import argparse,json,sys,os,hashlib,re
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/experimenter'),str(R/'code/runtime')]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def anchor(blocks,i,md):
 prev=next((b.get('content') for b in reversed(blocks[:i]) if b.get('content')),None);nxt=next((b.get('content') for b in blocks[i+1:] if b.get('content')),None)
 if not isinstance(prev,str) or not isinstance(nxt,str):return None
 if md.count(prev)!=1 or md.count(nxt)!=1:return None
 lo=md.index(prev)+len(prev);hi=md.index(nxt)
 return hi if lo<hi and not md[lo:hi].strip() else None

def coverage(blocks,i):
 x,y,X,Y=blocks[i]['bbox']
 for j,b in enumerate(blocks):
  if j==i or not b.get('content'):continue
  a,c,A,C=b['bbox'];inter=max(0,min(X,A)-max(x,a))*max(0,min(Y,C)-max(y,c))
  if inter>0:return True
 return False

def gate(im,blocks,i,md):
 from brace_tree_0135_v1 import risk
 from boxed_diagram_0133_v1 import view
 import numpy as np,cv2
 q=risk(im,blocks,i)
 if not q['accepted']:return q
 reason=None
 if view(im,blocks[i])['reason']=='no_complete_white_seam':reason='incomplete_white_seam'
 if coverage(blocks,i):reason='native_text_overlaps_image'
 if anchor(blocks,i,md) is None:reason='nonunique_or_nonempty_anchor'
 # Sparse tall components must bend: a straight rule has constant row centroid.
 a=np.asarray(im.crop(q['rect']).convert('L'));curves=[]
 for x,y,X,Y in q['braces']:
  ink=a[y:Y,x:X]<90;centers=[float(np.where(row)[0].mean()) for row in ink if row.any()]
  span=float(np.percentile(centers,90)-np.percentile(centers,10)) if centers else 0
  curves.append(span)
 if sum(s>=2 for s in curves)<2:reason='straight_strokes_not_braces'
 q['curvature_spans']=curves
 if reason:q.update(accepted=False,reason=reason)
 return q

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--pages',required=True);ap.add_argument('--out',required=True);ap.add_argument('--gpu',choices=['0','1','3'],required=True);ap.add_argument('--budget',type=int,default=8);ap.add_argument('--hidden',action='store_true');a=ap.parse_args();O=Path(a.out).resolve();base=Path(a.inputs).resolve();assert O.parent==R/'runs' and 0<=a.budget<=8
 if not a.hidden:
  if O.exists():
   assert json.loads((O/'runtime_inputs.json').read_text())['inputs']==str(base)
   if (O/'prepared.json').exists():return
  else:O.mkdir();(O/'runtime_inputs.json').write_text(json.dumps(dict(inputs=str(base))))
  from panel_hidden_0110_v2 import restricted
  args=['unshare','--net',*restricted(O,[sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--hidden'])];os.execvp(args[0],args)
 from single_model_selective_v1 import HIDDEN
 assert all(Path(p).stat().st_size==0 for p in HIDDEN)
 from PIL import Image
 images={p.stem:p for p in Path(a.pages).iterdir() if p.is_file()};bindings=[];rows=[];rejected=[]
 for f in sorted((base/'raw').glob('*.json')):
  src=images[f.stem];md=base/'markdown'/(f.stem+'.md');bindings.append(dict(raw=str(f),raw_sha256=sha(f),md_sha256=sha(md),source=str(src),source_sha256=sha(src)));raw=json.loads(f.read_bytes());seeds=[i for i,b in enumerate(raw['blocks']) if b['type']=='image' and b.get('angle',0)==0]
  if not seeds:continue
  im=Image.open(src).convert('RGB')
  for i in seeds:
   q=gate(im,raw['blocks'],i,md.read_bytes().decode())
   row=dict(source=str(src),raw=str(f),source_sha256=bindings[-1]['source_sha256'],owner=i,gate=q,view_pixel_sha256=hashlib.sha256(im.crop(q['rect']).tobytes()).hexdigest())
   (rows if q['accepted'] else rejected).append(row)
 assert len(bindings)==1651
 rows.sort(key=lambda q:(q['view_pixel_sha256'],q['owner']));counts={};queue=[]
 for q in rows:
  sh=q['source_sha256'];q['budget_admitted']=len(queue)<a.budget and counts.get(sh,0)<4
  if q['budget_admitted']:counts[sh]=counts.get(sh,0)+1;queue.append(dict(q,ordinal=len(queue)))
 (O/'plan.json').write_text(json.dumps(dict(GT_hidden=True,input_pages=len(bindings),risk_owners=len(rows),risk_pages=len(set(q['source_sha256'] for q in rows)),budget=a.budget,owner_cap=1,source_cap=4,gpu=a.gpu,rows=rows,queue=queue,rejected=rejected,bindings=bindings),ensure_ascii=False,indent=2))
 import io,torch
 from finite_request_identity_0101_v1 import helper,pix,key,MODEL,params,prompts
 from mineru_vl_utils.structs import ContentBlock
 from transformers import AutoProcessor
 torch.set_num_threads(2);proc=AutoProcessor.from_pretrained(MODEL,local_files_only=True);out=[]
 for q in queue:
  j=q['ordinal'];im=Image.open(q['source']).convert('RGB');rect=q['gate']['rect'];crop=im.crop(rect);crop.save(O/f'view{j}.png');data,ps,_,_=helper().prepare_for_extract(crop,[ContentBlock(type='text',bbox=[0.,0.,1.,1.],angle=0)]);pim=Image.open(io.BytesIO(data[0])).convert('RGB');assert ps[0]==prompts('text')[0]['text'];(O/f'prepared{j}.bin').write_bytes(data[0]);pim.save(O/f'prepared{j}.png')
  msg=[dict(role='system',content='You are a helpful assistant.'),dict(role='user',content=[dict(type='image',image=pim),dict(type='text',text=ps[0])])];s=proc.apply_chat_template(msg,tokenize=False,add_generation_prompt=True);v=proc(text=[s],images=[pim],return_tensors='pt');m=dict(prompt_tokens=int(v['input_ids'].shape[-1]),grid=v['image_grid_thw'].tolist(),tensor_sha256=hashlib.sha256(v['pixel_values'].numpy().tobytes()).hexdigest());assert m['prompt_tokens']+4096<=8192
  out.append(dict(**q,raw_sha256=sha(q['raw']),prompt=ps[0],parameters=params('text'),pixel_sha256=pix(pim),identity=key(pim.size,pix(pim),'text'),prepared_size=list(pim.size),prepared_sha256=sha(O/f'prepared{j}.bin'),processor=m,mapping=dict(rect=rect,affine=[crop.width/pim.width,0,rect[0],0,crop.height/pim.height,rect[1]])))
 (O/'prepared.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));(O/'budget.json').write_text(json.dumps(dict(maximum=a.budget,reserved=0,sources={},owners={},identities=[])))
 from dependency_lock_0111_v1 import create
 create(O/'dependencies.json',['code/experimenter/brace_production_0136_v1.py','code/experimenter/brace_transport_0136_v1.py','code/experimenter/brace_compose_0136_v1.py'])
 print(json.dumps(dict(pages=len(bindings),risk=len(rows),prepared=len(out))))
if __name__=='__main__':main()
