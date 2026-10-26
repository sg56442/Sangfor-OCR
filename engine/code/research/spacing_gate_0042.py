"""Input-only diagnostic risk and ordered conservation. No GT or page rules."""
import re,json,argparse,time
from pathlib import Path
from lxml import html
from table_mechanisms import grids
N=r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?'
ATOM=re.compile(r'(?:\('+N+r'\)|'+N+r')')
def compact(s):return re.sub(r'\s+','',s)
def atoms(s):
 s=compact(s);a=ATOM.findall(s);return a if ''.join(a)==s else []
def grid(s):
 g=grids(s)
 if len(g)!=1 or g[0]['holes'] or g[0]['conflicts'] or g[0]['span_beyond_rows']:return None
 return g[0]
def risk(s):
 g=grid(s)
 if not g:return dict(eligible=False,reason='invalid_grid')
 targets=[]
 for row in range(g['rows']):
  cs=[c for c in g['cells'] if c['row']==row]
  nums=[c['col'] for c in cs if len(atoms(c['text']))>=2]
  if len(nums)>=2 and cs and compact(cs[0]['text']):targets.append(dict(row=row,columns=nums))
 return dict(eligible=bool(targets) and 3<=g['width']<=12,reason='numeric_parallel_multibaseline_risk' if targets else 'no_parallel_compound_scalars',targets=targets,width=g['width'])
def conserve(old,new):
 a,b=grid(old),grid(new)
 if not a or not b:return dict(accepted=False,reason='invalid_grid')
 if a['width']!=b['width']:return dict(accepted=False,reason='schema_width')
 def seq(g):return [[(c['colspan'],compact(c['text'])) for c in sorted(g['cells'],key=lambda c:(c['row'],c['col'])) if c['col']==x and compact(c['text'])] for x in range(g['width'])]
 # Ordered column stream; each original spanning field retains its span signature.
 def stream(g):return [''.join(compact(c['text']) for c in sorted(g['cells'],key=lambda c:(c['row'],c['col'])) if c['col']==x) for x in range(g['width'])]
 if stream(a)!=stream(b):return dict(accepted=False,reason='ordered_column_content_loss_or_change')
 empty=lambda g:sum(not any(compact(c['text']) for c in g['cells'] if c['row']==r) for r in range(g['rows']))
 if empty(a)!=empty(b):return dict(accepted=False,reason='empty_rows_added_or_removed')
 # Headers are exact until first row with two numeric fields; no regenerated header substitution.
 def head(s,g):
  stop=next((r for r in range(g['rows']) if sum(bool(atoms(c['text'])) for c in g['cells'] if c['row']==r)>=2),g['rows'])
  rr=html.fromstring(s).xpath('.//tr');return [html.tostring(t,encoding='unicode') for t in rr[:stop]],stop
 ha,na=head(old,a);hb,nb=head(new,b)
 if ha!=hb:return dict(accepted=False,reason='header_changed')
 if any(c['rowspan']>1 or c['colspan']>1 for g,n in [(a,na),(b,nb)] for c in g['cells'] if c['row']>=n):return dict(accepted=False,reason='body_span_ambiguity')
 return dict(accepted=True,reason='ordered_conservation_pass_source_binding_still_required',body_start=na,old_rows=a['rows'],new_rows=b['rows'])
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--manifest',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();t=time.monotonic();pages=json.load(open(args.manifest));rows=[];count=0
 for p in pages:
  rp=Path(args.inputs)/'raw'/(p['id']+'.json');raw=json.load(rp.open())
  for i,b in enumerate(raw['blocks']):
   if b['type']!='table':continue
   count+=1;r=risk(b['content'])
   if r['eligible']:rows.append(dict(raw=str(rp),image=p['image'],owner=i,bbox=b['bbox'],angle=b.get('angle',0),risk=r))
 out=dict(pages=len(pages),tables=count,eligible_owners=len(rows),eligible_sources=len(set(r['image'] for r in rows)),rows=rows,wall_seconds=time.monotonic()-t,HTTP=0);Path(args.out).write_text(json.dumps(out,ensure_ascii=False,indent=2));print({k:v for k,v in out.items() if k!='rows'})
