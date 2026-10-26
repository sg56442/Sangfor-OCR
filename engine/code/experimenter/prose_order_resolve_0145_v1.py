"""Resolve source-column insertion before mutation; ambiguous new MD anchor keeps old route."""
from prose_order_0145_v1 import anchor

def resolve(q,native,image,markdown):
 new,proof=anchor(q,native,image)
 if proof['accepted']:
  target=new['insert_before'];content=native[target].get('content')
  if not content or markdown.count(content)!=1:
   return dict(q,order_proof=dict(proof,applied=False,transaction_fallback='nonunique insertion anchor'))
 return dict(new,order_proof=dict(proof,applied=proof['accepted']))
