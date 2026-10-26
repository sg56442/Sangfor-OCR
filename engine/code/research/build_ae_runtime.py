"""General A/E candidate builder from caller-supplied CURRENT native results and receipts.
No historical raw root, GT, source label or page-identity routing.
"""
import argparse,copy,io,hashlib,json
from pathlib import Path
from collections import defaultdict
from PIL import Image
from mineru_vl_utils import MinerUClient
from mineru_vl_utils.structs import ContentBlock
from table_mechanisms import grids,image_signals

def load(p):return json.loads(Path(p).read_text())
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2))
p=argparse.ArgumentParser();p.add_argument('--pages',required=True);p.add_argument('--native',required=True);p.add_argument('--http',required=True);p.add_argument('--endpoint',required=True);p.add_argument('--model',required=True);p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=False);(out/'crops').mkdir();native=Path(a.native)
client=MinerUClient(backend='http-client',model_name=a.model,server_url=a.endpoint,handle_equation_block=False,image_analysis=False,max_concurrency=45,max_connections=45,max_keepalive_connections=45,use_tqdm=False)
trace=defaultdict(list)
for line in (native/'route_trace.jsonl').read_text().splitlines():
 r=json.loads(line)
 if r['native_type']=='table':trace[r['page_id']].append(r['response_sha256'])
response={}
for line in (Path(a.http)/'http.jsonl').read_text().splitlines():
 r=json.loads(line)
 if r['stage']=='consumed':
  for c in r['response']['choices']:
   h=hashlib.sha256(c['message']['content'].encode()).hexdigest();response[h]=dict(finish_reason=c['finish_reason'],usage=r['response'].get('usage',{}),request_sha256=r['request_sha256'])
requests=[];proposals=[];receipts=[]
def prepare(image,blocks,bbox,ident,pid,indices,kind):
 # Native helper applies angle, table-image masking, and resize_by_need.
 block=ContentBlock(type='table',bbox=bbox,angle=0,content='')
 extras=[ContentBlock(type=b['type'],bbox=b['bbox'],angle=b.get('angle'),content=b.get('content')) for b in blocks if b['type']=='image']
 ims,prompts,params,ids=client.helper.prepare_for_extract(image,[block]+extras,None,False)
 assert ids[0]==0
 data=ims[0];assert isinstance(data,bytes)
 path=out/'crops'/(ident+'.png');path.write_bytes(data)
 with Image.open(io.BytesIO(data)) as im:pixel_hash=hashlib.sha256(im.convert('RGB').tobytes()).hexdigest();size=list(im.size)
 requests.append(dict(request_id=ident,image_path=str(path),pixel_sha256=pixel_hash,file_sha256=hashlib.sha256(data).hexdigest(),image_size=size,bbox=bbox,page_evidence=pid,indices=indices,kind=kind))
for page in load(a.pages):
 pid=page['id'];blocks=load(native/'raw'/(pid+'.json'))['blocks'];ts=[i for i,b in enumerate(blocks) if b['type']=='table'];order_ok=len(ts)==len(trace[pid]);native_receipts={i:response.get(h) for i,h in zip(ts,trace[pid])} if order_ok else {};page_rec=dict(page_evidence=pid,native_tables=len(ts),table_trace_count=len(trace[pid]),receipt_mapping_valid=order_ok,angle_fallbacks=[])
 with Image.open(page['image']) as image:
  image=image.convert('RGB');ordered=sorted(ts,key=lambda i:blocks[i]['bbox'][1])
  for i,j in zip(ordered,ordered[1:]):
   b,c=blocks[i],blocks[j];x,y=b['bbox'],c['bbox'];gap=y[1]-x[3];edge=max(abs(x[0]-y[0]),abs(x[2]-y[2]));ng=[grids(z.get('content','')) for z in (b,c)]
   if not(0<=gap<=.015 and edge<=.01 and all(len(g)==1 for g in ng) and ng[0][0]['width']==ng[1][0]['width']):continue
   if b.get('angle',0) or c.get('angle',0):page_rec['angle_fallbacks'].append([i,j]);continue
   bbox=[min(x[0],y[0]),x[1],max(x[2],y[2]),max(x[3],y[3])];ident=f'a{len(requests):05d}';prepare(image,blocks,bbox,ident,pid,[i,j],'merge');proposals.append(dict(kind='merge',page_evidence=pid,indices=[i,j],bbox=bbox,signal=dict(gap=gap,edge_misalignment=edge),request_ids=[ident]))
  for i in ts:
   receipt=native_receipts.get(i)
   if not receipt or receipt['finish_reason']!='length':continue
   b=blocks[i]
   if b.get('angle',0):page_rec['angle_fallbacks'].append([i]);continue
   x0,y0,x1,y1=b['bbox'];xy=[round(x0*image.width),round(y0*image.height),round(x1*image.width),round(y1*image.height)];roi=image.crop(xy);sig=image_signals(roi);gaps=sig['whitespace_bands']
   if not gaps:continue
   s,e=max(gaps,key=lambda g:g[1]-g[0]);cut=(xy[1]+(s+e)/2)/image.height;parts=[[x0,y0,x1,cut],[x0,cut,x1,y1]];ids=[]
   for box in parts:
    ident=f'a{len(requests):05d}';ids.append(ident);prepare(image,blocks,box,ident,pid,[i],'budget_split')
   proposals.append(dict(kind='budget_split',page_evidence=pid,indices=[i],bbox=b['bbox'],parts=parts,request_ids=ids,signal=dict(gap_px=e-s,finish_reason='length'),native_receipt=receipt))
 receipts.append(page_rec)
save(out/'requests.json',requests);save(out/'proposals.json',proposals);save(out/'builder_receipts.json',receipts);save(out/'inputs.json',dict(pages=str(Path(a.pages).resolve()),native=str(native.resolve()),http=str(Path(a.http).resolve()),scope='CURRENT native only; GT-free; explicit native angle fallback; native helper image preparation'))
print('pages',len(receipts),'calls',len(requests),'proposals',len(proposals),flush=True)
