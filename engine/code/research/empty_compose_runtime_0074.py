import sys,json,html,os,time,re
from pathlib import Path
from lxml import html as LH
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'code/research'),str(R/'code/experimenter'),str(R/'scripts')]
from spacing_gate_0042 import grid
from phase2_array_label_runtime_v1 import block_spans
from connective_span_0069 import paragraph_span
from repeated_runtime_0048b import patch
O=Path(sys.argv[1]);B=Path(json.load(open(O/'runtime_inputs.json'))['inputs']);t=time.monotonic();prepared=json.load(open(O/'prepared.json'));responses={x['ordinal']:x for x in json.load(open(O/'responses.json'))};edits={};decisions=[]
for q in prepared:
 v=responses.get(q['ordinal'],{});d=dict(ordinal=q['ordinal'],accepted=False);decisions.append(d)
 if v.get('status')!='CONSUMED' or v.get('finish')!='stop' or not v.get('text','').strip():d['reason']='transport_or_empty';continue
 old=q['block']['content'];g=grid(old);positions=[i for i,c in enumerate(g['cells']) if c['row']==q['row'] and c['col']==q['col']];root=LH.fromstring(old);cells=root.xpath('.//td|.//th');i=positions[0]
 if len(positions)!=1 or len(cells)!=len(g['cells']) or len(cells[i]) or (cells[i].text or '').strip():d['reason']='not_literal_empty';continue
 # Locate complete serialized empty-cell occurrence by HTML token position, preserve all outside bytes.
 matches=list(re.finditer(r'<(?:td|th)\b[^>]*>.*?</(?:td|th)>',old,re.S|re.I));m=matches[i]
 if not re.fullmatch(r'<(?:td|th)\b[^>]*>\s*</(?:td|th)>',m.group(),re.I):d['reason']='markup_ambiguous';continue
 entry=m.group();at=entry.index('>')+1;payload='<br/>'.join(html.escape(z.strip()) for z in v['text'].strip().splitlines());new=old[:m.start()]+entry[:at]+payload+entry[at:]+old[m.end():];edits.setdefault(Path(q['raw']).name,[]).append((q['owner'],old,new,d));d['reason']='complete_response_literal_empty_cell'
P=O/'selected_predictions';P.mkdir();(P/'raw').mkdir();(P/'markdown').mkdir()
for rp in (B/'raw').glob('*.json'):
 mp=B/'markdown'/(rp.stem+'.md');rb=rp.read_bytes();mb=mp.read_bytes();raw=json.loads(rb);re=[];me=[]
 for i,old,new,d in edits.get(rp.name,[]):
  try:
   assert raw['blocks'][i]['content']==old;span=paragraph_span(mb,old,new);assert not any(span[0]<e and span[1]>s for s,e,_ in me);me.append(span);re.append((*block_spans(rb,raw)[i],json.dumps(dict(raw['blocks'][i],content=new),ensure_ascii=False).encode()));d['accepted']=True
  except (AssertionError,KeyError,IndexError):d['reason']='raw_MD_binding_fallback'
 for sub,p,data in [('raw',rp,patch(rb,re)),('markdown',mp,patch(mb,me))]:
  if data==p.read_bytes():os.link(p,P/sub/p.name)
  else:(P/sub/p.name).write_bytes(data)
(O/'compose.json').write_text(json.dumps(dict(decisions=decisions,seconds=time.monotonic()-t),ensure_ascii=False,indent=2))
