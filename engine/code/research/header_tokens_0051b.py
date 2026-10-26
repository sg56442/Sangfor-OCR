"""Strict input boundary and surgical attribute-value edits; no scientific thresholds."""
import re
from html.parser import HTMLParser
from table_mechanisms import grids
ATTR=re.compile(r'''\s+([^\s=<>/"']+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s<>`="']+)))?''')
OPEN=re.compile(r'''<([A-Za-z][A-Za-z0-9:_-]*)(?:[^<>"']|"[^"]*"|'[^']*')*>''',re.S)
def attributes(tag):
 m=re.match(r'<[A-Za-z][A-Za-z0-9:_-]*',tag);assert m,'Malformed tag';pos=m.end();result={}
 while pos<len(tag)-1:
  if tag[pos:-1].strip() in ('','/'):break
  a=ATTR.match(tag,pos);assert a,'Ambiguous attribute syntax'
  key=a.group(1).lower();assert key not in result,'Duplicate attribute'
  value=next((k for k in [2,3,4] if a.group(k) is not None),None)
  result[key]=(a.group(value),a.span(value)) if value else (None,None);pos=a.end()
 return result
class Boundary(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=False);self.tables=0;self.depth=0
 def handle_starttag(self,tag,attrs):
  attributes(self.get_starttag_text())
  if tag=='table':self.tables+=1;self.depth+=1;assert self.depth==1,'Nested table'
 def handle_endtag(self,tag):
  if tag=='table':self.depth-=1;assert self.depth==0,'Unbalanced table'
 def handle_startendtag(self,tag,attrs):raise AssertionError('Self-closing markup ambiguous')
def validate(old):
 try:
  p=Boundary();p.feed(old);p.close();assert p.tables==1 and p.depth==0,'Multiple or missing table'
  gs=grids(old);assert len(gs)==1,'Nonunique grid';g=gs[0]
  assert not(g['holes'] or g['conflicts'] or g['span_beyond_rows']),'Invalid grid'
  return g
 except (AssertionError,ValueError,IndexError):return None
def span2(segment):
 m=OPEN.match(segment);assert m,'Ambiguous opening cell';tag=m.group();attrs=attributes(tag)
 if 'colspan' in attrs:
  value,bounds=attrs['colspan'];assert value=='1' and bounds,'Expected explicit colspan1'
  s,e=bounds;tag=tag[:s]+'2'+tag[e:]
 else:
  end=re.match(r'<[A-Za-z][A-Za-z0-9:_-]*',tag).end();tag=tag[:end]+' colspan="2"'+tag[end:]
 return tag+segment[m.end():]
