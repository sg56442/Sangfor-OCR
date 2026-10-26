import os,json,sys,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'scripts'),str(R/'code/research'),str(R/'code/experimenter')]
from single_model_selective_v1 import hidden
if '--isolated' not in sys.argv:subprocess.run(hidden(['unshare','--net',sys.executable,__file__,'--isolated']),check=True);raise SystemExit
from phase2_array_label_runtime_v1 import block_spans
from repeated_runtime_0048b import patch
from spacing_apply_0046 import span
from spacing_state_0044 import load,save
from column_view_0059 import measure
from column_edits_0063 import assemble,complete
from spacing_state_0044 import sha
from collections import Counter
from PIL import Image
O=Path(os.environ['SPACING_OUT']);P=O;cfg=load(P/'inputs.json');save(O/'inputs.json',cfg);src=Path(cfg['inputs']);qs=load(P/'processor_plan.json');ledger=load(P/'ledger.json');assert not ledger.get('protocol_fatal');pending={a:{} for a in ['generator','selected']};records=[]
for path,h in load(O/'input_binding.json').items():assert sha(path)==h,('input mismatch',path)
counts=Counter((q['raw'],q['owner']) for q in qs)
for q in qs:
 if counts[(q['raw'],q['owner'])]!=1:continue
 raw=load(q['raw']);b=raw['blocks'][q['owner']];rs=[r for r in ledger['records'].values() if r.get('index')==q['index']];new=complete(rs)
 if new is None:continue
 im=Image.open(q['source']);w,h=im.size;m=measure(im,b)
 if not m or not m.get('expanded_box'):continue
 eb=m['expanded_box'];bbox=[v/s for v,s in zip(eb,[w,h,w,h])];overlaps=[]
 for i,z in enumerate(raw['blocks']):
  if i==q['owner'] or not z.get('content'):continue
  a=z.get('bbox');
  if not a:continue
  intersection=max(0,min(a[2],bbox[2])-max(a[0],bbox[0]))*max(0,min(a[3],bbox[3])-max(a[1],bbox[1]))
  if intersection>0:overlaps.append(i)
 accept=m['risk'] and not overlaps and bool(new.strip()) and '<table' not in new
 d=dict(accepted=accept,reason='full_parent_gutter_region_exclusive_text' if accept else 'geometry_or_other_owner_conflict',other_owners=overlaps,runtime_risk=m,source_mapping='Wholeoriginalparent plus rightglyph continuation to persistentgutter; completeText source order, allotherowners unchanged',newtype='text');records.append(dict(index=q['index'],source=q['source'],owner=q['owner'],before=b['content'],candidate=new,decision=d))
 rp=Path(q['raw']);nb=dict(b,type='text',content=new,bbox=bbox)
 for arm in pending:
  if arm=='generator' or accept:pending[arm].setdefault(rp.stem,[]).append((q['owner'],nb))
assembly=[]
for arm in pending:
 for stem,updates in list(pending[arm].items()):
  rb=(src/'raw'/(stem+'.json')).read_bytes();md=(src/'markdown'/(stem+'.md')).read_bytes();nr,nm,error=assemble(rb,md,updates);pending[arm][stem]=(nr,nm);assembly.append(dict(arm=arm,stem=stem,owners=[i for i,b in updates],fallback=error))
save(O/'assembly.json',assembly)
for arm in pending:
 for sub in ['raw','markdown']:
  target=O/(arm+'_predictions')/sub;target.mkdir(parents=True,exist_ok=False)
  for p in (src/sub).iterdir():
   if p.stem in pending[arm]:(target/p.name).write_bytes(pending[arm][p.stem][0 if sub=='raw' else 1])
   else:os.link(p,target/p.name)
save(O/'decisions.json',records);print([(r['index'],r['decision']) for r in records])
