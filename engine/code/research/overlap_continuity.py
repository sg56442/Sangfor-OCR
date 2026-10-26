"""Source-interval anchored overlap assembly; no GT or native topology requirements."""
from table_mechanisms import grids
from lxml import html
import re,copy,html as entities

def textkey(s):
 return re.sub(r'\s+','',entities.unescape(s))
def parsed(s):
 gs=grids(s)
 if len(gs)!=1 or gs[0]['holes'] or gs[0]['conflicts'] or gs[0]['span_beyond_rows']:return None
 root=html.fromstring('<div>'+s+'</div>');table=root.xpath('.//table')[0];rows=table.xpath('.//tr');g=gs[0]
 signatures=[tuple((c['col'],c['rowspan'],c['colspan'],textkey(c['text'])) for c in g['cells'] if c['row']==i) for i in range(g['rows'])]
 return g,rows,signatures

def reconstruct(top,overlap,bottom,intervals):
 # These intervals MUST refer to the same original full-width pixel ROI.
 a,m,b=intervals
 if not (a[0]==0 and a[1]==m[1] and m[0]==b[0] and 0<=m[0]<m[1]<=b[1]):return None,{'reason':'source_interval_mismatch'}
 p=[parsed(x) for x in [top,overlap,bottom]]
 if any(x is None for x in p):return None,{'reason':'invalid_local_table'}
 (tg,tr,ts),(mg,mr,ms),(bg,br,bs)=p;n=len(ms)
 if len({tg['width'],mg['width'],bg['width']})!=1:return None,{'reason':'column_identity_disagreement'}
 if n==0 or len(ts)<n or len(bs)<n:return None,{'reason':'overlap_rows_not_contained'}
 # Match only suffix/prefix corresponding to the EXACT SAME source overlap.
 # Repeated strings elsewhere cannot be used as an anchor.
 if ts[-n:]!=ms or bs[:n]!=ms:return None,{'reason':'shared_interval_structure_or_content_disagreement'}
 offset=len(ts)-n
 if any(c['row']<offset<c['row']+c['rowspan'] for c in tg['cells']):return None,{'reason':'top_span_crosses_overlap_start'}
 if any(c['row']<n<c['row']+c['rowspan'] for c in bg['cells']):return None,{'reason':'bottom_span_crosses_overlap_end'}
 out=html.Element('table')
 for row in tr[:offset]+mr+br[n:]:out.append(copy.deepcopy(row))
 rendered=html.tostring(out,encoding='unicode')
 if parsed(rendered) is None:return None,{'reason':'assembled_span_invalid'}
 return rendered,dict(reason='three_views_exact_shared_source_interval',overlap_rows=n,top_prefix_rows=offset,bottom_suffix_rows=len(bs)-n,column_count=mg['width'],intervals=intervals)

def select(native,candidates):
 # Source-anchored assembly is prerequisite, not HTML-validity selection.
 # Require content preservation; candidate topology remains unconstrained.
 ng=parsed(native)
 if ng is None:return None,'invalid_native'
 content=textkey(''.join(c['text'] for c in ng[0]['cells']))
 valid=[]
 for c in candidates:
  if c is None:continue
  cg=parsed(c)
  if cg and textkey(''.join(z['text'] for z in cg[0]['cells']))==content:valid.append(c)
 if not valid:return None,'no_source_mapped_content_preserving_candidate'
 if len(valid)>1 and parsed(valid[0])[2]!=parsed(valid[1])[2]:return None,'cross_cut_topology_disagreement'
 return valid[0],'source_interval_consensus_content_preserved'
