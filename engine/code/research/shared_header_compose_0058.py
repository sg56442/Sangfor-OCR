import os,json,sys,hashlib
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'scripts'),str(R/'code/research'),str(R/'code/experimenter')]
from phase2_mixed_prose_runtime_v1 import owner_tokens
from repeated_runtime_0048b import patch
from spacing_apply_0046 import span
from shared_header_0056 import select
from spacing_state_0044 import save,load,sha
from mineru_vl_utils.post_process import simple_process
from mineru_vl_utils.structs import ContentBlock
O=Path(os.environ['SPACING_OUT']);cfg=load(O/'inputs.json');src=Path(cfg['inputs']);qs=load(O/'processor_plan.json');state=load(O/'ledger.json');assert not state.get('protocol_fatal')
for kind in ['dependencies','input_binding']:
 for p,h in load(O/(kind+'.json')).items():assert sha(p)==h
pending={a:{} for a in ['generator','selected']};decisions=[]
for q in qs:
 t=q['tasks'][0];key=hashlib.sha256(json.dumps(dict(pixel=t['pixel_sha256'],prompt=t['prompt'],parameters=t['parameters']),sort_keys=True).encode()).hexdigest();z=state['records'].get(key,{});rp=Path(q['raw']);raw=load(rp);old=raw['blocks'][q['owner']]['content'];rec=dict(index=q['index'],source=q['source'],owner=q['owner'],status=z.get('status'));decisions.append(rec)
 if z.get('status')!='COMPLETE':continue
 new=simple_process([ContentBlock(type='table',bbox=[0,0,1,1],content=z['text'])])[0].content;d=select(Image.open(q['source']),old,new,raw['blocks'],q['owner'],q['geometry']);rec.update(before=old,candidate=new,decision=d)
 for arm in pending:
  if arm=='selected' and not d['accepted']:continue
  try:
   rb=rp.read_bytes();md=(src/'markdown'/(rp.stem+'.md')).read_bytes();rm=owner_tokens(rb,raw);re=[(*rm[(q['owner'],'content')],json.dumps(new,ensure_ascii=False).encode())];me=[span(md,old,new)]
   if arm=='selected':
    cs=d['caption_owner'];cap=raw['blocks'][cs]['content'];re.append((*rm[(cs,'content')],b'null'));me.append(span(md,cap,''))
   item=pending[arm].setdefault(rp.stem,dict(rb=rb,md=md,re=[],me=[]))
   for edits,prior in [(re,item['re']),(me,item['me'])]:
    ordered=sorted(prior+edits);assert all(a[1]<=b[0] for a,b in zip(ordered,ordered[1:]))
   item['re']+=re;item['me']+=me
  except (AssertionError,ValueError,KeyError) as e:rec[arm+'_fallback']=str(e)
for arm,items in pending.items():
 for sub in ['raw','markdown']:
  out=O/(arm+'_predictions')/sub;out.mkdir(parents=True,exist_ok=False)
  for p in (src/sub).iterdir():
   if p.stem in items:
    it=items[p.stem];data=patch(it['rb' if sub=='raw' else 'md'],it['re' if sub=='raw' else 'me']);(out/p.name).write_bytes(data)
   else:os.link(p,out/p.name)
save(O/'decisions.json',decisions);print([(d['index'],d.get('decision')) for d in decisions])
