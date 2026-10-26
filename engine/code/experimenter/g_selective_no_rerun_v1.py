"""G v4 source-preserving block API; no historical paths or scoring inputs."""
import copy,re,hashlib,json
from g_v4.content_guards_v3 import formula_canonical,independent_formula
RULE_ID='G_SOURCE_GRAMMAR_NO_RERUN_V1'
def independent_v4(text):
 c=formula_canonical(text)
 if not independent_formula(text):return False
 connector=r'\\(?:text|mathrm|operatorname)\{(?:and|or|if|for|where|when|with|suchthat)\}'
 if re.search(r'(?:'+connector+r')$',c,re.I) or re.match(r'^(?:'+connector+r')',c,re.I):return False
 if re.search(r'\\(?:land|lor|wedge|vee|implies|Rightarrow)$',c):return False
 # An index's enumerated range is an applicability fragment, not an independent derivation.
 if re.match(r'^[A-Za-z](?:_\{[^{}]+\}|_[A-Za-z0-9])?=',c) and ',' in c and re.search(r'\\(?:ldots|cdots|dots)|\.\.\.',c):return False
 return True

def select_and_apply(blocks,proposals,answers,native_evidence):
 """Inputs belong to current run. Page identities/GT are never branch features."""
 groups={}
 for a in answers:
  assert a['kind'] in ('left','right'), 'Unexpected G rerun or unknown response'
  assert a['kind'] not in groups.setdefault(a['proposal'],{}), 'Duplicate response'
  groups[a['proposal']][a['kind']]=a
 modified=copy.deepcopy(blocks);decisions=[];changes=[]
 for pi,p in enumerate(proposals):
  idx=p['index'];b=blocks[idx];assert b['bbox']==p['bbox'],'Proposal/native geometry mismatch';g=groups.get(pi,{})
  rec={'proposal':pi,'original_block_index':idx,'bbox':b['bbox'],'rule_id':RULE_ID,'triggered':bool(p['triggered']),'selected':False}
  if not all(k in g for k in ['left','right']):rec['reason']='missing_consumed_candidate';decisions.append(rec);continue
  left,right=g['left']['content'],g['right']['content'];joined=formula_canonical(left)+formula_canonical(right);current_preserved=joined==formula_canonical(b.get('content') or '');grammar=independent_v4(left) and independent_v4(right)
  rec.update(current_native_preserved=current_preserved,rerun_native_preserved=None,rerun_native_evidence_available=False,independent_complete_expressions=grammar,selected=bool(p['triggered'] and current_preserved and grammar),reason='accepted_source_and_grammar' if p['triggered'] and current_preserved and grammar else 'fallback_source_or_grammar_or_untriggered')
  if rec['selected']:
   parts=[]
   for k in ['left','right']:
    nb=copy.deepcopy(b);nb.update(content=g[k]['content'],bbox=g[k]['bbox']);parts.append(nb)
   changes.append((idx,parts))
  decisions.append(rec)
 for idx,parts in sorted(changes,reverse=True):modified[idx:idx+1]=parts
 return modified,{'rule_id':RULE_ID,'native_evidence':native_evidence,'source_blocks_sha256':hashlib.sha256(json.dumps(blocks,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),'configured':len(proposals),'triggered':sum(x['triggered'] for x in decisions),'applied':len(changes),'consumed':len(answers),'selected':len(changes),'fallback':len(proposals)-len(changes),'decisions':decisions,'changed':bool(changes)}
