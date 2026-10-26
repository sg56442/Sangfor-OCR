import json,sys,time,shutil,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'code/experimenter'))
from skew_select_0146_v1 import select
O=Path(sys.argv[1]).resolve();B=Path(json.loads((O/'runtime_inputs.json').read_text())['inputs']);qs=json.loads((O/'prepared.json').read_text());rs=json.loads((O/'responses.json').read_text());t=time.monotonic();receipts=[]
for variant in ['generator','selected']:
 dest=O/(variant+'_predictions');shutil.copytree(B,dest,dirs_exist_ok=True)
 for q in qs:
  a=next((r for r in rs if r.get('ordinal')==q['ordinal'] and r.get('status')=='CONSUMED'),None)
  if a is None:receipts.append(dict(variant=variant,accepted=False,reason='missing_or_failed_request',ordinal=q['ordinal']));continue
  stem=Path(q['raw']).stem;p=dest/'raw'/f'{stem}.json';md=dest/'markdown'/f'{stem}.md';raw=json.loads(p.read_bytes());s=md.read_bytes().decode();decision,why=select(raw['blocks'],q['gate'],s,a.get('text'),a.get('finish'))
  if decision:
   for i,para in zip(decision['indices'],decision['paragraphs']):raw['blocks'][i]['content']=para
   out=s[:decision['start']]+decision['replacement']+s[decision['start']+len(decision['span']):]
   md.write_bytes(out.encode());p.write_text(json.dumps(raw,ensure_ascii=False,indent=2))
   for i,(old,new) in enumerate(zip(json.loads(Path(q['raw']).read_bytes())['blocks'],raw['blocks'])):
    if i not in decision['indices']:assert old==new
   receipts.append(dict(variant=variant,accepted=True,reason=why,owners=decision['indices'],page=stem,all_outside_owners_and_MD_bytes_preserved=True,whole_response_used=True))
  elif variant=='generator':
   # Diagnostic complete group response remains measured even when alignment fails.
   ids=q['gate']['indices'];old=[raw['blocks'][i]['content'] for i in ids];span='\n\n'.join(old);assert s.count(span)==1
   md.write_text(s.replace(span,a['text'],1));raw['blocks'][ids[0]]['content']=a['text']
   for i in ids[1:]:raw['blocks'][i]['content']=''
   p.write_text(json.dumps(raw,ensure_ascii=False,indent=2));receipts.append(dict(variant=variant,accepted=True,selector_rejection=why,diagnostic_only=True))
  else:receipts.append(dict(variant=variant,accepted=False,reason=why))
(O/'compose.json').write_text(json.dumps(dict(seconds=time.monotonic()-t,receipts=receipts),indent=2));print(receipts)
