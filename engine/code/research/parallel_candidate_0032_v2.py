"""A zero-call experimental parallel-column regrouping; image/current raw only."""
import argparse,json,copy,time
from pathlib import Path
from lxml import html,etree
from PIL import Image
from parallel_lists_0032_v3 import lexical,geometry

def process(image,raw):
 result=copy.deepcopy(raw);audit=[]
 for index,b in enumerate(raw['blocks']):
  if b['type']!='table':continue
  g,parents=lexical(b.get('content') or '')
  if not parents:continue
  geo=geometry(image,b,g,parents);selected=[p for p in geo['proposals'] if p['eligible']]
  if not selected:continue
  W,H=image.size;foreign=[]
  for j,other in enumerate(raw['blocks']):
   if j==index:continue
   bb=[round(v*(W if k%2==0 else H)) for k,v in enumerate(other['bbox'])]
   for p in selected:
    a=p['bounds']
    if min(a[2],bb[2])-max(a[0],bb[0])>2 and min(a[3],bb[3])-max(a[1],bb[1])>2:foreign.append(j)
  if foreign:audit.append(dict(index=index,accepted=False,reason='foreign_owner',foreign=foreign));continue
  root=html.fromstring('<div>'+b['content']+'</div>');table=root.xpath('.//table')[0];rows=table.xpath('./tr');nodes=table.xpath('./tr/td|./tr/th')
  if len(nodes)!=len(g['cells']):continue
  for p in sorted(selected,key=lambda p:p['parent']['row'],reverse=True):
   par=p['parent'];start=par['row'];end=start+par['rowspan'];new=html.Element('tr');parentidx=g['cells'].index(par);parentnode=copy.deepcopy(nodes[parentidx]);parentnode.attrib.pop('rowspan',None);new.append(parentnode)
   for col in range(1,g['width']):
    ids=[k for k,c in enumerate(g['cells']) if c['col']==col and start<=c['row']<end];dest=html.Element('td');before=''.join(''.join(nodes[k].itertext()) for k in ids)
    for num,k in enumerate(ids):
     src=nodes[k]
     if num:br=etree.SubElement(dest,'br');br.tail=src.text
     else:dest.text=src.text
     for child in src:dest.append(copy.deepcopy(child))
    assert ''.join(dest.itertext())==before
    new.append(dest)
   pos=table.index(rows[start]);table.insert(pos,new)
   for row in rows[start:end]:table.remove(row)
  candidate=''.join(html.tostring(n,encoding='unicode') for n in root);ng=lexical(candidate)[0];assert ng and not any(ng[k] for k in ['holes','conflicts','span_beyond_rows'])
  # Every original text character remains exactly once; order is intentionally percolumn.
  from collections import Counter
  assert Counter(''.join(root.itertext()))==Counter(''.join(html.fromstring('<div>'+b['content']+'</div>').itertext()))
  result['blocks'][index]['content']=candidate;audit.append(dict(index=index,accepted=True,groups=selected,before=b['content'],after=candidate))
 return result,audit

def main():
 p=argparse.ArgumentParser();p.add_argument('--image',required=True);p.add_argument('--raw',required=True);p.add_argument('--out',required=True);a=p.parse_args();raw=json.loads(Path(a.raw).read_text())
 with Image.open(a.image) as im:result,audit=process(im,raw)
 Path(a.out).write_text(json.dumps(dict(raw=result,audit=audit),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
