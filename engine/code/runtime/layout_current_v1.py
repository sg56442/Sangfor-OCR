"""Caller-current adapters. No IO, GT, page identity, or response cache lookup."""
import copy,hashlib,json
from local_layout_apply_v1 import apply
from layout_row_pairs_v1 import pair_rows

def signature(block):
 return hashlib.sha256(json.dumps({k:block.get(k) for k in ('type','bbox','content','angle')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def pixel_hash(image):return hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()
def bind(blocks,image,p):
 q=copy.deepcopy(p);q['origin_signatures']=[signature(blocks[i]) for i in p['indices']];q['source_pixels_sha256']=pixel_hash(image);q['source_size']=list(image.size);return q

def select_and_apply(blocks,image,proposals,responses,family):
 valid=[];rejected=[];claimed=set()
 for p in proposals:
  q=copy.deepcopy(p);ids=[];reason=None
  if list(image.size)!=p['source_size'] or pixel_hash(image)!=p['source_pixels_sha256']:reason='stale_source_pixels'
  for sig in p['origin_signatures']:
   hits=[i for i,b in enumerate(blocks) if signature(b)==sig]
   if len(hits)!=1:reason='stale_or_ambiguous_origin';break
   ids.append(hits[0])
  if len(ids)!=len(p['indices']) or ids!=sorted(ids) or any(i in claimed for i in ids):reason=reason or 'origin_order_or_conflict'
  if reason:rejected.append(dict(proposal=p['proposal_id'],accepted=False,reason=reason));continue
  q['indices']=ids;valid.append(q);claimed.update(ids)
 if family=='group':new,recs=apply(blocks,valid,responses,'group')
 else:
  new=copy.deepcopy(blocks);_,recs=apply(blocks,valid,responses,'dense');ps={p['proposal_id']:p for p in valid}
  for rec in recs:
   if not rec['accepted']:continue
   p=ps[rec['proposal']];content,detail=pair_rows(responses[p['proposal_id']]);rec['row_pair']=detail;rec['accepted']=content is not None
   if content is not None:new[p['indices'][0]]['content']=content
   else:rec['reason']=detail['reason']
 for rec in recs:
  p=next(p for p in valid if p['proposal_id']==rec['proposal']);rec['source_origins']=[{'current_index':i,'signature':signature(blocks[i])} for i in p['indices']];rec['source_pixels_sha256']=p['source_pixels_sha256']
 return new,recs+rejected
