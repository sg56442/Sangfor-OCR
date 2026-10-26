"""Frozen native MinerU two-step extraction; exactly one model endpoint."""
import http_audit
import argparse,hashlib,json,re,time,collections
from pathlib import Path
from PIL import Image
from mineru_vl_utils import MinerUClient
from mineru_vl_utils.post_process import json2md
from mineru_vl_utils.structs import ExtractResult

def save(p,d):
 q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(d,ensure_ascii=False,indent=2));q.replace(p)
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--expected-count',type=int,required=True);p.add_argument('--pages',required=True);p.add_argument('--model',required=True);p.add_argument('--weight-sha256',required=True);p.add_argument('--port',type=int,required=True);p.add_argument('--output',required=True);a=p.parse_args()
out=Path(a.output);out.mkdir(parents=True,exist_ok=False);(out/'raw').mkdir();(out/'markdown').mkdir();pages=json.load(open(a.pages));assert len(pages)==a.expected_count and len({x['id'] for x in pages})==a.expected_count
client=MinerUClient(backend='http-client',model_name=a.model,server_url=f'http://127.0.0.1:{a.port}',handle_equation_block=False,image_analysis=False,max_concurrency=45,max_connections=45,max_keepalive_connections=45,use_tqdm=False)
assert client.prompts['table']=='\nTable Recognition:'
state=dict(status='running',model=a.model,model_weight_sha256=a.weight_sha256,endpoint_port=a.port,expected_count=a.expected_count,processed_count=0,started_at=time.time(),single_checkpoint=True,route_counts={})
counts=collections.Counter();save(out/'worker_receipt.json',state)
try:
 with (out/'route_trace.jsonl').open('w') as trace:
  for offset in range(0,len(pages),32):
   group=pages[offset:offset+32];images=[];t=time.time()
   try:
    for page in group:
     with Image.open(page['image']) as im:images.append(im.convert('RGB'))
    layout=client.batch_layout_detect(images)
    assert len(layout)==len(group)
    for page,blocks in zip(group,layout):
     counts['[layout]']+=1;trace.write(json.dumps(dict(page_id=page['id'],native_type='[layout]',role='single_candidate',model=a.model,endpoint_port=a.port,layout_blocks_sha256=digest(json.dumps(list(blocks),sort_keys=True,default=str))))+'\n')
    save(out/f'layout_{offset:05d}.json',dict(pages=[p['id'] for p in group],layouts=[list(x) for x in layout]))
    prep=client.helper.batch_prepare_for_extract(client.executor,images,layout,None,None)
    ims,prompts,params,indices=client._flatten_prepared_inputs(prep)
    answers=client._batch_predict(ims,prompts,params,None,None)
    assert len(answers)==len(indices)
    for (pi,bi),prompt,answer in zip(indices,prompts,answers):
     block=layout[pi][bi];block.content=answer.text;block.scored=answer.scored;counts[block.type]+=1
     trace.write(json.dumps(dict(page_id=group[pi]['id'],native_type=block.type,role='single_candidate',model=a.model,endpoint_port=a.port,prompt_sha256=digest(prompt),response_sha256=digest(answer.text)))+'\n')
    processed=client.helper.batch_post_process(client.executor,layout)
    for page,blocks in zip(group,processed):
     blocks=list(ExtractResult(blocks))
     for block in blocks:
      if block.get('type')=='equation' and block.get('content'):block['content']=re.sub(r'\\tag\s*\{[^}]*\}','',block['content'])
     save(out/'raw'/(page['id']+'.json'),dict(page=page['id'],blocks=blocks))
     md=out/'markdown'/(page['id']+'.md');tmp=md.with_suffix('.md.tmp');tmp.write_text(json2md(blocks));tmp.replace(md)
    trace.flush();state.update(processed_count=offset+len(group),route_counts=dict(counts),elapsed_seconds=time.time()-state['started_at']);save(out/'worker_receipt.json',state)
    print(json.dumps(dict(processed_count=state['processed_count'],batch_seconds=time.time()-t,elapsed_seconds=state['elapsed_seconds'])),flush=True)
   finally:
    for im in images:im.close()
 expected={x['id'] for x in pages}
 for folder,ext in [('markdown','*.md'),('raw','*.json')]:assert {p.stem for p in (out/folder).glob(ext)}==expected
 assert counts['[layout]']==a.expected_count
 state.update(status='complete',is_complete=True,empty_pages=[p.stem for p in (out/'markdown').glob('*.md') if not p.read_text().strip()])
except BaseException as e:state.update(status='failed',error=repr(e));raise
finally:state.update(finished_at=time.time(),elapsed_seconds=time.time()-state['started_at']);save(out/'worker_receipt.json',state)
