"""Zero-call omitted-table candidate from native label/body row layout.
No page identity, GT, vocabulary whitelist, or learned thresholds.
"""
import copy
from html import escape
from missing_table_geometry import proposals

def apply(blocks):
 blocks=copy.deepcopy(blocks);replace={};remove=set();decisions=[]
 for p in sorted(proposals(blocks),key=lambda p:(-p['columns'],p['column_center_error'])):
  items=sorted([blocks[i] for i in p['indices']],key=lambda b:b['bbox'][1]);n=p['columns'];rows=[sorted(items[:n],key=lambda b:b['bbox'][0]),sorted(items[n:],key=lambda b:b['bbox'][0])];typed=all(b['type']=='title' for b in rows[0]) and all(b['type']=='text' for b in rows[1]);accept=typed and not remove.intersection(p['indices']);decisions.append(dict(rule='NATIVE_TYPED_GRID_V1',indices=p['indices'],bbox=p['bbox'],typed_row_support=typed,selected=bool(accept)))
  if not accept:continue
  markup='<table>'+''.join('<tr>'+''.join('<td>'+escape(b.get('content',''))+'</td>' for b in row)+'</tr>' for row in rows)+'</table>';b=dict(blocks[min(p['indices'])]);b.update(type='table',bbox=p['bbox'],content=markup,angle=0);b.pop('merge_prev',None);replace[min(p['indices'])]=b;remove.update(p['indices'])
 return [replace[i] if i in replace else b for i,b in enumerate(blocks) if i not in remove or i in replace],decisions,bool(replace)
