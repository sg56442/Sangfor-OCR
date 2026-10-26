"""Current-input shared-schema selection; source ownership and monotone content binding.
No GT, source identity, date strings, fixed answers or manual split boundary.
"""
import re
from collections import Counter
from lxml import html
from table_mechanisms import grids

def compact(s):return re.sub(r'\s+','',s)
def cellgrid(s):
 g=grids(s)
 if len(g)!=1 or g[0]['conflicts'] or g[0]['holes'] or g[0]['span_beyond_rows']:raise ValueError('invalid')
 return g[0]
def rows(g):
 r=[[] for _ in range(g['rows'])]
 for c in g['cells']:r[c['row']].append(c)
 return [sorted(z,key=lambda c:c['col']) for z in r]
def text(s,kind):return ''.join(html.fromstring(s).itertext()) if kind=='table' else s

def select(proposal,raw,new,finished=True):
 if not proposal['eligible']:return dict(accept=False,reason='preflight:'+proposal['reason'])
 if not finished:return dict(accept=False,reason='not_normal_stop')
 try:g=cellgrid(new);upper=cellgrid(raw['blocks'][proposal['upper']]['content']);left=cellgrid(raw['blocks'][proposal['left']]['content']);right=cellgrid(raw['blocks'][proposal['right']]['content'])
 except Exception:return dict(accept=False,reason='invalid_partition')
 if g['width']!=proposal['width']:return dict(accept=False,reason='schema_width_conflict')
 # Require unchanged upper cells including exact anchor/span; generated lower owns later rows only.
 key=lambda c:(c['row'],c['col'],c['rowspan'],c['colspan'],compact(c['text']))
 if [key(c) for c in g['cells'] if c['row']<upper['rows']]!=[key(c) for c in upper['cells']]:return dict(accept=False,reason='upper_schema_or_content_conflict')
 alltext=''.join(text(raw['blocks'][i]['content'],raw['blocks'][i]['type']) for i in proposal['indices'])
 if Counter(compact(alltext))!=Counter(compact(text(new,'table'))):return dict(accept=False,reason='content_multiset_conflict')
 tail=rows(g)[upper['rows']:]
 for i in proposal['bridge']:
  if not tail or compact(tail[0][0]['text'])!=compact(raw['blocks'][i]['content']) or tail[0][0]['col']!=0 or any(compact(c['text']) for c in tail[0][1:]):return dict(accept=False,reason='bridge_ownership_conflict')
  tail=tail[1:]
 if len(tail)!=len(proposal['source_left_bands']):return dict(accept=False,reason='left_source_baseline_count_conflict')
 if any(len(r)!=g['width'] or any(c['colspan']!=1 or c['rowspan']!=1 for c in r) for r in tail):return dict(accept=False,reason='lower_partition_ambiguity')
 if ''.join(compact(r[0]['text']) for r in tail)!=''.join(compact(c['text']) for c in left['cells']):return dict(accept=False,reason='left_monotone_content_conflict')
 aligned=[]
 # Only source-aligned left baselines may own numeric/value cells.
 from PIL import Image
 with Image.open(proposal['image']) as im:h=im.height
 ltop=round(raw['blocks'][proposal['left']]['bbox'][1]*h);rtop=round(raw['blocks'][proposal['right']]['bbox'][1]*h)
 ly=[(s+e)/2+ltop for s,e in proposal['source_left_bands']];ry=[(s+e)/2+rtop for s,e in proposal['source_right_bands']]
 indices=[]
 for y in ry:
  choices=[i for i,z in enumerate(ly) if abs(y-z)<=proposal['row_tolerance']]
  if len(choices)!=1:return dict(accept=False,reason='nonunique_baseline_owner')
  indices.append(choices[0])
 if len(set(indices))!=len(indices):return dict(accept=False,reason='duplicate_baseline_owner')
 expected=[[compact(c['text']) for c in rr] for rr in rows(right)]
 actual=[[compact(c['text']) for c in tail[i][1:]] for i in indices]
 if actual!=expected:return dict(accept=False,reason='right_row_column_content_conflict')
 if any(any(compact(c['text']) for c in rr[1:]) for i,rr in enumerate(tail) if i not in indices):return dict(accept=False,reason='parent_row_has_unowned_values')
 return dict(accept=True,reason='upper_schema_bridge_monotone_labels_source_baselines_value_binding',source_owner_rows=indices,all_characters_preserved=True,scope='finite same-input source support; not proof for all future documents')
