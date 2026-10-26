"""Source-compatible span representation, not content recovery."""
import re
import numpy as np
from header_census_0049 import risks
from table_mechanisms import runs,grids
from lxml import html
from header_tokens_0051b import validate,span2,attributes,OPEN
lexical=risks
def candidate(im,old):
 checked=validate(old)
 if checked is None:return old,dict(accepted=False,lexical=0,reason='ambiguous_html_boundary')
 rr=risks(old);d=dict(accepted=False,lexical=len(rr),reason='ambiguous_geometry')
 if len(rr)!=1:return old,d
 q=rr[0];ink=np.asarray(im.convert('L'))<180
 # Ignore full-width table rules, retaining all text pixels for geometry only.
 ink[ink.mean(axis=1)>.65]=False
 bands=[(a,b) for a,b in runs(ink.mean(axis=1)>.015) if b-a>=2];n=len(q['body'])
 if len(bands)<n+2:return old,d
 body=bands[-n:];top=body[0][0];bottom=body[-1][1];columns=[(a,b) for a,b in runs(ink[top:bottom].any(axis=0))]
 # Merge glyph columns across gaps smaller than half median text height; preserve inter-column whitespace.
 height=float(np.median([b-a for a,b in body]));groups=[]
 for a,b in columns:
  if groups and a-groups[-1][1]<height*.6:groups[-1][1]=b
  else:groups.append([a,b])
 g=grids(old)[0]
 if len(groups)!=g['width']:return old,dict(d,reason='column_count',groups=groups)
 indexes=[q['header']['col'],q['blank']['col'],q['sibling']['col'],q['sibling']['col']+1]
 for a,b in body:
  if any(not ink[a:b,groups[c][0]:groups[c][1]].any() for c in indexes):return old,d
 ha,hb=bands[-n-1];a,b=groups[q['blank']['col']]
 if ink[ha:hb,a:b].any():return old,dict(d,reason='independent_symbol_header_ink')
 root=html.fromstring(old);trs=root.xpath('.//tr');r=q['header']['row'];cells=trs[r].xpath('./td|./th');gridcells=[c for c in g['cells'] if c['row']==r];j=next(i for i,c in enumerate(gridcells) if c['col']==q['header']['col']);cell=cells[j];blank=cells[j+1]
 assert ''.join(blank.itertext()).strip()==''
 # Exact byte-preserving HTML token edit: only opening td and adjacent empty td.
 matches=list(re.finditer(r'<(?:td|th)\b[^>]*>.*?</(?:td|th)>',old,re.S|re.I));idx=g['cells'].index(q['header']);m=matches[idx];bm=matches[idx+1];assert bm.start()>=m.end()
 segment=m.group()
 try:segment=span2(segment)
 except AssertionError:return old,dict(d,reason='ambiguous_colspan_attribute')
 empty=re.fullmatch(r'<t[dh]\b[^>]*>(\s*)</t[dh]>',bm.group(),re.I|re.S)
 if empty is None:return old,dict(d,reason='empty_header_markup_ambiguous')
 ba=attributes(OPEN.match(bm.group()).group())
 if any(k not in ('colspan','rowspan') or v[0]!='1' for k,v in ba.items()):return old,dict(d,reason='empty_header_nonspan_attributes')
 new=old[:m.start()]+segment+old[m.end():bm.start()]+empty.group(1)+old[bm.end():]
 ng=validate(new)
 if ng is None or (ng['rows'],ng['width'])!=(g['rows'],g['width']):return old,dict(d,reason='post_edit_grid_invalid')
 assert ''.join(html.fromstring(new).itertext())==''.join(root.itertext())
 return new,dict(accepted=True,lexical=1,reason='source_compatible_parent_coverage',bands=bands,columns=groups,meaning='representation_only')
