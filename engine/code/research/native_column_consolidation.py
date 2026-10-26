"""Source-column alignment of existing native cells; no GT or page identity."""
import copy,itertools,re,html as entities
import numpy as np
from lxml import html,etree
from table_mechanisms import grids
from source_column_views import row_boundaries

def key(s):
 return re.sub(r'\s+','',entities.unescape(s)).replace('{','').replace('}','')

def source_rows(proposal):
 sequences=[]
 for x in proposal['inputs']:
  ys=row_boundaries(x['original_image']);gaps=np.diff(ys);typical=float(np.median(gaps))
  # Border rules clipped by the native ROI are endpoints, not extra short rows.
  inner=[y for y in ys[1:-1] if min(y,ys[-1]-y)>.25*typical]
  sequences.append(inner)
 counts=[len(v) for v in sequences];n=max(set(counts),key=counts.count);usable=[i for i,v in enumerate(sequences) if len(v)==n]
 if len(usable)<max(2,(len(sequences)+1)//2):return None,dict(reason='no_shared_separator_tracks',sequences=sequences)
 xs=np.array([sum(proposal['columns'][i])/2 for i in usable]);tracks=[]
 for k in range(n):
  yy=np.array([sequences[i][k] for i in usable]);fit=np.polyfit(xs,yy,1);res=float(np.max(np.abs(np.polyval(fit,xs)-yy)))
  if res>max(3,proposal['source_image'].height*.006) or abs(fit[0])>.05:return None,dict(reason='inconsistent_source_row_tracks',residual=res)
  tracks.append(dict(y=yy.tolist(),slope=float(fit[0]),residual=res))
 return n+1,dict(reason='shared_sloped_source_separator_tracks',sequences=sequences,columns=usable,tracks=tracks)

def consolidate(native,proposal,answers):
 gs=grids(native);c=len(proposal['columns'])
 if len(gs)!=1:return None,dict(reason='not_single_table')
 g=gs[0];w=g['width']
 if w<=c:return None,dict(reason='no_excess_native_columns',native_width=w,physical_columns=c)
 if w>24 or g['conflicts'] or g['holes'] or g['span_beyond_rows'] or any(x['rowspan']!=1 or x['colspan']!=1 for x in g['cells']):return None,dict(reason='ambiguous_native_span_or_grid')
 coltext=[]
 for inp in proposal['inputs']:
  a=answers.get(inp['key'])
  if not a or a.get('http_receipt',{}).get('finish_reason')!='stop':return None,dict(reason='missing_current_response')
  ag=grids(a['html'])
  if len(ag)!=1:return None,dict(reason='unusable_column_text')
  coltext.append(key(''.join(x['text'] for x in ag[0]['cells'])))
 rows=[[x for x in g['cells'] if x['row']==r] for r in range(g['rows'])]
 def sequence(left,right):return key(''.join(x['text'] for row in rows for x in row[left:right]))
 # Dynamic partition search: only adjacent native columns may combine.
 solutions=[]
 def visit(ci,start,bounds):
  if len(solutions)>1:return
  if ci==c:
   if start==w:solutions.append(bounds)
   return
  for end in range(start+1,w-(c-ci-1)+1):
   if sequence(start,end)==coltext[ci]:visit(ci+1,end,bounds+[end])
 visit(0,0,[0])
 if len(solutions)!=1:return None,dict(reason='column_content_partition_not_unique',solutions=len(solutions),native_width=w,physical_columns=c)
 bounds=solutions[0];nr,geometry=source_rows(proposal)
 if nr!=g['rows']:return None,dict(reason='native_rows_not_supported_by_source_tracks',native_rows=g['rows'],source_rows=nr,geometry=geometry,partition=bounds)
 root=html.fromstring('<div>'+native+'</div>');oldrows=root.xpath('.//table')[0].xpath('.//tr');table=html.Element('table');mapping=[]
 for ri,row in enumerate(oldrows):
  old=row.xpath('./td|./th');tr=etree.SubElement(table,'tr')
  for ci,(left,right) in enumerate(zip(bounds,bounds[1:])):
   if right-left==1:tr.append(copy.deepcopy(old[left]))
   else:
    td=etree.SubElement(tr,'td')
    for j in range(left,right):
     node=copy.deepcopy(old[j])
     if j>left:
      if len(td):td[-1].tail=(td[-1].tail or '')+' '
      else:td.text=(td.text or '')+' '
     if node.text:
      if len(td):td[-1].tail=(td[-1].tail or '')+node.text
      else:td.text=(td.text or '')+node.text
     for child in node:td.append(child)
   mapping.append(dict(row=ri,source_column=ci,native_cells=list(range(ri*w+left,ri*w+right))))
 rendered=html.tostring(table,encoding='unicode');cg=grids(rendered)[0]
 assert key(''.join(x['text'] for x in g['cells']))==key(''.join(x['text'] for x in cg['cells']))
 assert sorted(i for m in mapping for i in m['native_cells'])==list(range(len(g['cells'])))
 return rendered,dict(reason='unique_source_column_content_partition',partition=bounds,native_width=w,physical_columns=c,geometry=geometry,cell_conservation=mapping,selected=True)
