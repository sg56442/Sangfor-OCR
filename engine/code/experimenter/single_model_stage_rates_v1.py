"""Read stage-local trigger/accept counts; never infer missing measurements."""
import json
from pathlib import Path

def measure(run):
 run=Path(run)
 def read(rel):return json.loads((run/rel).read_text()) if (run/rel).exists() else None
 pipeline=read('pipeline.json');total=pipeline['configured_pages'];result={}
 composed=read('aecg/composition_receipt.json');counts=composed['counts'] if composed else {}
 layout=read('layout_combined/composition_receipt.json');lc=layout['counts'] if layout else {}
 for name,rel,key,accepted in [
  ('AE','ae/proposals.json','page_evidence',counts.get('ae_selected')),
  ('G','g/probe/proposals.json','page',counts.get('g_selected')),
  ('E','e/proposals.json','page',None),
  ('layout_group','layout/group/proposals.json','page',lc.get('group_accepted')),
  ('layout_dense','layout/dense/proposals.json','page',lc.get('dense_accepted'))]:
  proposals=read(rel)
  if proposals is None:result[name]={'status':'NOT_RECORDED'};continue
  active=[p for p in proposals if p.get('triggered',True) and not p.get('normal_control',False)]
  if name=='E':
   receipts=read('e/applied/receipt.json')
   accepted=sum(bool(r['accepted']) for r in receipts) if receipts is not None else None
  result[name]=dict(configured=len(proposals),triggered=len(active),triggered_pages=len({p[key] for p in active}),
    trigger_page_fraction=len({p[key] for p in active})/total,accepted=accepted,
    accept_fraction=accepted/len(active) if accepted is not None and active else None,
    fallback=len(active)-accepted if accepted is not None else None)
 for rel in ['aecg/composition_receipt.json','aecge/composition_receipt.json','aecgeq/composition_receipt.json','aecgem/composition_receipt.json','layout_combined/composition_receipt.json','combined/composition_receipt.json']:
  rec=read(rel)
  if rec is not None:result[rel]={'counts_as_recorded':rec.get('counts'),'path':str(run/rel)}
 return result
