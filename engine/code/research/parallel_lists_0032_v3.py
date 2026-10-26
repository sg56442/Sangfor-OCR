"""Source/native-only parent-band relation proposals. No DB, model, GT, identity routing."""
import json,re,sys,time,hashlib
from pathlib import Path
from collections import Counter
import numpy as np,cv2
from PIL import Image
from table_mechanisms import grids,runs
R=Path(__file__).resolve().parents[2];O=R/'reports/researcher_phase2_0032'
def lexical(s):
 gs=grids(s)
 if len(gs)!=1:return None,[]
 g=gs[0]
 if any(g[k] for k in ['holes','conflicts','span_beyond_rows']):return g,[]
 parents=[]
 for c in g['cells']:
  if c['col']!=0 or c['colspan']!=1 or c['rowspan']<2 or not c['text'].strip():continue
  kids=[z for z in g['cells'] if z['col']>0 and c['row']<=z['row']<c['row']+c['rowspan']]
  cols={z['col'] for z in kids if z['text'].strip()}
  if len(cols)>=2 and sum(bool(re.search('[A-Za-z\u4e00-\u9fff]',z['text'])) for z in kids)>=4:parents.append(c)
 return g,parents

def geometry(im,b,g,parents):
 w,h=im.size;box=[round(v*(w if i%2==0 else h)) for i,v in enumerate(b['bbox'])];a=np.asarray(im.convert('L').crop(box));H,W=a.shape
 if b.get('angle',0)!=0:return dict(reason='rotation',proposals=[])
 ink=(a<150).astype('uint8');hr=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(30,W//3)),np.uint8));vr=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((max(30,H//3),1),np.uint8));glyph=ink & (1-(hr|vr))
 n,_,stats,_=cv2.connectedComponentsWithStats(glyph,8);hh=[s[3] for s in stats[1:] if s[4]>=8 and s[3]>=4 and s[3]<H*.15 and s[2]<W*.1]
 if not hh:return dict(reason='no_glyph_scale',proposals=[])
 gh=float(np.median(hh));gut=[(l,r) for l,r in runs(glyph[int(.2*H):].mean(0)<.005) if r-l>=max(6,.6*gh) and l>.03*W and r<.97*W]
 if len(gut)!=g['width']-1:return dict(reason='column_gutters_not_unique',gutters=gut,proposals=[],glyph_height=gh)
 cuts=[0]+[(l+r)//2 for l,r in gut]+[W]
 def bands(lo,hi,t=0,bot=H):
  rr=[]
  for l,r in runs(glyph[t:bot,lo:hi].sum(1)>=2):
   l+=t;r+=t
   if rr and l-rr[-1][1]<.2*gh:rr[-1][1]=r
   else:rr.append([l,r])
  return [p for p in rr if p[1]-p[0]>=.45*gh]
 left=bands(1,cuts[1]-2);nativeleft=sorted([c for c in g['cells'] if c['col']==0],key=lambda c:c['row'])
 if len(left)!=len(nativeleft):return dict(reason='parent_sequence_not_unique',left_bands=left,native_parent_count=len(nativeleft),gutters=gut,proposals=[])
 centers=[sum(p)/2 for p in left];bound=[0];blank=runs(glyph.sum(1)==0)
 for u,v in zip(centers,centers[1:]):
  rules=[(l+r)//2 for l,r in runs(hr.mean(1)>.9) if u<l and r<v]
  if len(rules)==1:
   bound.append(rules[0]);continue
  if len(rules)>1:return dict(reason='multiple_parent_separators',proposals=[])
  spaces=[(r-l,(l+r)//2) for l,r in blank if l>u and r<v and r-l>=3]
  if not spaces:return dict(reason='no_complete_group_seam',proposals=[])
  bound.append(max(spaces)[1])
 bound.append(H);proposals=[]
 for par in parents:
  k=nativeleft.index(par);t,bot=bound[k:k+2];cols=[bands(cuts[j]+2,cuts[j+1]-2,t,bot) for j in range(1,len(cuts)-1)];counts=[len(z) for z in cols];pairs=[]
  for j in range(len(cols)):
   for z in range(j+1,len(cols)):
    x,y=cols[j],cols[z]
    if min(len(x),len(y))<2:continue
    matched=sum(any(abs(sum(p)/2-sum(q)/2)<=.4*gh for q in y) for p in x)
    pairs.append(dict(columns=[j+1,z+1],aligned_fraction=matched/max(len(x),len(y)),counts=[len(x),len(y)]))
  asynchronous=any(p['counts'][0]!=p['counts'][1] and p['aligned_fraction']<.7 for p in pairs)
  children=[c for c in g['cells'] if c['col']>0 and par['row']<=c['row']<par['row']+par['rowspan']]
  simple=all(c['colspan']==1 and c['rowspan']==1 for c in children)
  numeric=sum(bool(re.search(r'\d',c['text'])) for c in children if c['text'].strip())
  internal_rules=[]
  for col in range(1,len(cuts)-1):
   l,r=cuts[col:col+2];tt=int(t+gh*.6);bb=int(bot-gh*.6)
   if bb>tt and r-l>6 and (hr[tt:bb,l+2:r-2].mean(1)>.8).any():internal_rules.append(col)
  native_counts=[sum(bool(c['text'].strip()) for c in children if c['col']==j) for j in range(1,g['width'])]
  complete_counts=counts==native_counts
  proposals.append(dict(parent=par,bounds=[box[0],box[1]+t,box[2],box[1]+bot],column_cuts=[box[0]+x for x in cuts],bands=cols,counts=counts,pair_alignment=pairs,asynchronous=asynchronous,simple_children=simple,numeric_children=numeric,internal_rules=internal_rules,native_atom_counts=native_counts,complete_counts=complete_counts,eligible=asynchronous and simple and numeric==0 and not internal_rules and complete_counts,reason='source_asynchronous_parallel_list_proposal' if asynchronous and simple and numeric==0 else 'records_or_shared_values_or_unproven'))
 return dict(reason='parent_bands_mapped',box=box,glyph_height=gh,gutters=gut,left_bands=left,bounds=bound,proposals=proposals)

def main():
 start=time.monotonic();rows=[];tables=0
 for p in json.loads((R/'code/runtime/runs/native_full1651_gpu5_v2/pages.json').read_text()):
  path=R/'runs/phase2_quantity_panel_B_v1/predictions/raw'/(p['id']+'.json');raw=json.loads(path.read_text())
  for i,b in enumerate(raw['blocks']):
   if b['type']!='table':continue
   tables+=1;g,parents=lexical(b.get('content') or '')
   if not parents:continue
   with Image.open(p['image']) as im:geo=geometry(im,b,g,parents)
   rows.append(dict(source=p['image'],raw=str(path.relative_to(R)),owner=i,parents=parents,geometry=geo))
 q=dict(pages=1651,tables=tables,lexical_tables=len(rows),physical_sources=len({r['source'] for r in rows}),geometry_counts=Counter(r['geometry']['reason'] for r in rows),proposals=sum(p['eligible'] for r in rows for p in r['geometry']['proposals']),wall_seconds=time.monotonic()-start,rows=rows)
 (O/'census_v3.json').write_text(json.dumps(q,ensure_ascii=False,indent=2));print({k:v for k,v in q.items() if k!='rows'})
if __name__=='__main__':main()
