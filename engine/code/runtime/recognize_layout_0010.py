import argparse,pathlib,json,os,time,hashlib,io
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--port',type=int,required=True);a=p.parse_args();R=pathlib.Path(__file__).resolve().parents[2];r=pathlib.Path(a.run);assert r.resolve().is_relative_to(R);os.environ['FT1021_AUDIT_DIR']=str(r/'audit');import http_audit
from mineru_vl_utils import MinerUClient
from mineru_vl_utils.structs import ExtractResult
c=MinerUClient(backend='http-client',model_name=json.load(open(R/'agents/shared/runtime.json'))['model'],server_url=f'http://127.0.0.1:{a.port}',handle_equation_block=False,image_analysis=False,max_concurrency=45,max_connections=45,max_keepalive_connections=45,use_tqdm=False,max_retries=2)
qs=json.load(open(r/'requests.json'));results=[];prepared=[];start=time.time()
try:
 for offset in range(0,len(qs),32):
  batch=qs[offset:offset+32];payloads=[]
  for q in batch:
   im=Image.open(q['image']).convert('RGB');data=c.helper.prepare_for_layout(im);payloads.append(data);size=Image.open(io.BytesIO(data)).size;q.update(prepared_sha256=hashlib.sha256(data).hexdigest(),prepared_size=size,affine_prepared_to_page=[q['size'][0]/size[0],0,q['affine_candidate_to_page'][2],0,q['size'][1]/size[1],q['affine_candidate_to_page'][5]]);prepared.append(q)
  ans=c._batch_predict(payloads,c.prompts['[layout]'],c.sampling_params['[layout]'],None,None)
  for q,x in zip(batch,ans):results.append(dict(proposal=q['proposal'],raw_answer=x.text,blocks=list(ExtractResult(c.helper.parse_layout_output(x.text)))))
 (r/'recognition.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));(r/'prepared_requests.json').write_text(json.dumps(prepared,indent=2));status='complete'
except BaseException:status='failed';raise
finally:(r/'recognition_receipt.json').write_text(json.dumps(dict(status=status,configured=len(qs),consumed=len(results),incremental_calls=len(qs),gpu_service_wall_seconds=time.time()-start,max_retries=2),indent=2))
