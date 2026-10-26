"""Whole-group, monotone paragraph ownership. No GT or source identity routing."""
import re,difflib,math
def norm(s):return re.sub(r'\s+','',s)
def select(blocks,gate,md,response,finish):
 if not gate.get('accepted'):return None,'risk_rejected'
 ids=gate['indices'];old=[blocks[i].get('content') for i in ids]
 if any(not isinstance(s,str) or not s.strip() for s in old):return None,'null_owner'
 if any(blocks[i].get('content') for i in range(min(ids),max(ids)+1) if i not in ids):return None,'interleaved_owner'
 if finish!='stop' or not isinstance(response,str) or not response.strip():return None,'incomplete'
 new=re.split(r'\n\s*\n',response.strip().replace('\r\n','\n'))
 if len(new)!=len(old) or any('\n' in s or any(t in s for t in ['```','<table','<img']) for s in new):return None,'paragraph_shape'
 sep='\r\n\r\n' if '\r\n' in md else '\n\n';span=sep.join(old)
 if md.count(span)!=1:return None,'nonunique_span'
 at=md.index(span)
 if (at and not md[:at].endswith(sep)) or (at+len(span)<len(md) and not md[at+len(span):].startswith(sep)):return None,'embedded_span'
 long=[i for i,s in enumerate(old) if len(norm(s))>=12]
 if not long or sum(norm(old[i])==norm(new[i]) for i in long)<math.ceil(len(long)/2):return None,'complete_anchor_loss'
 if norm(old[0])!=norm(new[0]):return None,'start_anchor_loss'
 if any(not .4<=len(norm(b))/max(1,len(norm(a)))<=2.5 or difflib.SequenceMatcher(None,norm(a),norm(b),autojunk=False).ratio()<.4 for a,b in zip(old,new)):return None,'owner_alignment_uncertain'
 return dict(indices=ids,paragraphs=new,span=span,replacement=sep.join(new),start=at),'complete_group_monotone'
