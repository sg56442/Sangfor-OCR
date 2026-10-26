"""Native recognition of bounded runtime-only ROI manifest, with HTTP receipts."""
import argparse,json,pathlib,os,time,io,hashlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/"code/runtime"))
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--port',type=int,default=28521);a=p.parse_args();root=pathlib.Path(__file__).resolve().parents[2];run=pathlib.Path(a.run).resolve();assert run.is_relative_to(root);assert not (run/'recognition.json').exists();os.environ['FT1021_AUDIT_DIR']=str(run/'audit');import http_audit
from mineru_vl_utils import MinerUClient
from native_content import process_content
model=json.load(open(root/'agents/shared/runtime.json'))['model'];client=MinerUClient(backend='http-client',model_name=model,server_url=f'http://127.0.0.1:{a.port}',handle_equation_block=False,image_analysis=False,max_concurrency=45,max_connections=45,max_keepalive_connections=45,use_tqdm=False,max_retries=3)
requests=json.load(open(run/'requests.json'));payloads=[]
for j in requests:
 with Image.open(j['image']) as im:
  im=client.helper.resize_by_need(im.convert('RGB'));buf=io.BytesIO();im.save(buf,format='PNG');data=buf.getvalue();payloads.append(data);j['prepared_size']=im.size;j['prepared_sha256']=hashlib.sha256(data).hexdigest();j['prepared_pixel_sha256']=hashlib.sha256(im.tobytes()).hexdigest();j['affine_prepared_to_page']=[j['affine_candidate_to_page'][0]*j['size'][0]/im.width,0,j['affine_candidate_to_page'][2],0,j['affine_candidate_to_page'][4]*j['size'][1]/im.height,j['affine_candidate_to_page'][5]]
(run/'prepared_requests.json').write_text(json.dumps(requests,indent=2));start=time.time();results=[]
try:
 answers=client._batch_predict(payloads,[client.prompts[j['task']] for j in requests],[client.sampling_params[j['task']] for j in requests],None,None)
 assert len(answers)==len(requests), "Incomplete response batch"
 for j,ans in zip(requests,answers):
  row=dict(j,raw_answer=ans.text,content=process_content(client,{'type':'text' if j['task']=='[default]' else j['task'],'bbox':j['bbox'],'angle':0},ans.text));results.append(row)
 (run/'recognition.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));status='complete'
except BaseException as e:status='failed';(run/'recognition_failure.json').write_text(json.dumps({'error':repr(e),'class':'RUN_FAILURE','raw_retained':True}));raise
finally:(run/'recognition_receipt.json').write_text(json.dumps({'status':status,'configured':len(requests),'consumed':len(results),'incremental_calls':len(requests),'max_retries':3,'gpu_service_wall_seconds':time.time()-start,'selected':0,'scored':0},indent=2))
print(json.dumps({'status':status,'calls':len(results)}))
