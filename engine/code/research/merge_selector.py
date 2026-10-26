"""Runtime-only merge selector; frozen v1 gates, explicit overlap resolution."""
from collections import Counter
from lxml import html
from table_mechanisms import grids

def chars(s):return Counter(c for c in ''.join(html.fromstring('<div>'+s+'</div>').itertext()) if not c.isspace())
def choose(native,proposal,candidate):
 sig=proposal['signal'];ng=[grids(b['content']) for b in native];cg=grids(candidate)
 if len(cg)!=1 or any(len(x)!=1 for x in ng):return False,{'reason':'table_count'}
 a,b=[x[0] for x in ng];c=cg[0];nc=chars(''.join(x['content'] for x in native));cc=chars(candidate);coverage=sum((nc&cc).values())/max(1,sum(nc.values()));ratio=sum(cc.values())/max(1,sum(nc.values()))
 accept=(0<=sig['gap']<=.015 and sig['edge_misalignment']<=.01 and a['width']==b['width']==c['width'] and not c['holes'] and not c['conflicts'] and c['rows']>=max(a['rows'],b['rows']) and coverage>=.95 and .85<=ratio<=1.15)
 return accept,dict(char_coverage=coverage,char_count_ratio=ratio,widths=[a['width'],b['width'],c['width']],rows=[a['rows'],b['rows'],c['rows']],signal=sig)
def disjoint(proposals,reverse=False):
 used=set();selected=[]
 for p in sorted(proposals,key=lambda p:(p['signal']['gap'],p['bbox'][1],p['bbox'][0]),reverse=reverse):
  if not used.intersection(p['indices']):selected.append(p);used.update(p['indices'])
 return selected

def glyphs(markup):
 import re
 s=''.join(html.fromstring('<div>'+markup+'</div>').itertext())
 # Only presentation commands; structural math commands are retained as glyph words.
 s=re.sub(r'\\(?:mathrm|mathbf|mathit|text|operatorname)\b','',s)
 s=re.sub(r'\\[()\[\]]','',s)
 return Counter(c for c in s if not c.isspace() and c not in '{}')

def choose_v2(blocks,proposal,candidate,image):
 import re,numpy as np
 native=[blocks[i] for i in proposal['indices']];sig=proposal['signal'];ng=[grids(b['content']) for b in native];cg=grids(candidate)
 if len(cg)!=1 or any(len(x)!=1 for x in ng):return False,{'reason':'table_count'}
 a,b=[x[0] for x in ng];c=cg[0];nc=glyphs(''.join(x['content'] for x in native));cc=glyphs(candidate);coverage=sum((nc&cc).values())/max(1,sum(nc.values()));ratio=sum(cc.values())/max(1,sum(nc.values()))
 box=proposal['bbox'];captions=[z for z in blocks if z['type']=='table_caption' and 0<=box[1]-z['bbox'][3]<=.06 and z['bbox'][0]<=box[2] and z['bbox'][2]>=box[0]]
 numbered=[z for z in captions if re.search(r'(?i)\btable\s*[0-9IVX]+|表\s*[0-9一二三四五六七八九十]+',z.get('content') or '')]
 between=[z for z in blocks if z['type'] in ['table_caption','title'] and native[0]['bbox'][3]<=z['bbox'][1] and z['bbox'][3]<=native[1]['bbox'][1]]
 y0=round(native[0]['bbox'][3]*image.height);y1=round(native[1]['bbox'][1]*image.height);x0=round(box[0]*image.width);x1=round(box[2]*image.width)
 gap=image.crop((x0,y0,x1,max(y0+1,y1))).convert('L');ink=float((np.asarray(gap)<180).mean())
 geometry=(0<=sig['gap']<=.015 and sig['edge_misalignment']<=.01 and a['width']==b['width']==c['width'] and a['width']>=3 and min(a['rows'],b['rows'])>=3)
 accept=(geometry and bool(numbered) and not between and ink<.08 and not c['holes'] and not c['conflicts'] and c['rows']>=max(a['rows'],b['rows']) and coverage>=.95 and .85<=ratio<=1.15)
 return accept,dict(glyph_coverage=coverage,glyph_ratio=ratio,numbered_caption_support=bool(numbered),intervening_caption=len(between),gap_ink_fraction=ink,geometry=geometry,widths=[a['width'],b['width'],c['width']])
