"""Minimal syntax guard. No visual/source identity or old/new content comparison."""
import re
from html.parser import HTMLParser
from lxml import html
class Closed(HTMLParser):
 def __init__(self):super().__init__();self.stack=[];self.bad=False;self.tables=0
 def handle_starttag(self,tag,attrs):
  if tag in ('br','hr','img'):return
  if tag=='table':self.tables+=1
  if tag in ('script','style','iframe'):self.bad=True
  if tag in ('td','th') and (not self.stack or self.stack[-1]!='tr'):self.bad=True
  if tag=='tr' and (not self.stack or self.stack[-1] not in ('table','tbody','thead','tfoot')):self.bad=True
  self.stack.append(tag)
 def handle_endtag(self,tag):
  if not self.stack or self.stack.pop()!=tag:self.bad=True
 def handle_startendtag(self,tag,attrs):
  if tag not in ('br','hr','img'):self.bad=True

def legal(markup,raw_answer,finish):
 if finish!='stop' or not isinstance(markup,str):return False,'incomplete_response'
 if '<fcel>' in raw_answer and not raw_answer.rstrip().endswith('<nl>'):return False,'incomplete_OTSL_row'
 p=Closed()
 try:p.feed(markup);p.close()
 except Exception:return False,'HTML_parse'
 if p.bad or p.stack or p.tables!=1 or not markup.strip().startswith('<table') or not markup.strip().endswith('</table>'):return False,'HTML_closure'
 try:root=html.fromstring(markup)
 except Exception:return False,'HTML_parse'
 for cell in root.xpath('.//td|.//th'):
  s=''.join(cell.itertext());stack=[]
  for tok in re.findall(r'\\[()\[\]]|(?<!\\)\$\$|(?<!\\)\$',s):
   if tok in (r'\(',r'\['):
    if stack:return False,'nested_math_delimiter'
    stack.append(tok)
   elif tok in (r'\)',r'\]'):
    if not stack or (stack.pop(),tok) not in [(r'\(',r'\)'),(r'\[',r'\]')]:return False,'unclosed_math_delimiter'
   else:
    if stack and stack[-1]==tok:stack.pop()
    elif stack:return False,'nested_math_delimiter'
    else:stack.append(tok)
  if stack:return False,'unclosed_math_delimiter'
 return True,'complete_table_and_math_syntax'
