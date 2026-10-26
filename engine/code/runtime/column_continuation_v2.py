"""Column continuation with repeated-entry protection; current pixels/blocks only.
Frozen v1 geometry retained. No page IDs, GT, vocabulary or source categories.
"""
import re,copy
import numpy as np
from column_continuation_v1 import apply as v1_apply,lines
END_INDEX=re.compile(r'(?:[（(]\s*\d{1,4}(?:\s*[-–,，]\s*\d{1,4})*\s*[）)]|\.{2,}\s*\d{1,4})\s*$')
START_ITEM=re.compile(r'^\s*(?:[•●■▪◦]|\[\d{1,4}\]|\(?\d{1,3}[.)、．]|[A-Za-z][.)])\s*')
def entry_structure(image,block):
 text=block.get('content')or'';rows=[s.strip() for s in text.splitlines() if s.strip()];short=[s for s in rows if len(s)<=64];ends=sum(bool(END_INDEX.search(s)) for s in short);starts=sum(bool(START_ITEM.search(s)) for s in short)
 evidence=dict(nonempty_rows=len(rows),short_rows=len(short),terminal_index_rows=ends,marked_rows=starts,protected=False)
 if len(rows)<2 or len(short)<2:return evidence
 pix=lines(image,block['bbox']);ls=pix['lines'];evidence['pixel_lines']=len(ls)
 # Repeated independent records plus physical separate rows, not prose punctuation.
 if len(ls)>=2 and (ends>=2 or starts>=2):evidence.update(protected=True,reason='repeated_index_or_item_markers');return evidence
 # Multiline short record lists without numbers: repeated ragged line ends and
 # distinct spatial row gaps. At least four lines avoids two-line prose wraps.
 if len(short)>=4 and len(short)>=.8*len(rows) and len(ls)>=4:
  h=float(np.median([p[3]-p[1] for p in ls]));width=pix['size'][0];ragged=sum(p[2]<width-2*h for p in ls);gaps=[b[1]-a[3] for a,b in zip(ls,ls[1:])];evidence.update(ragged_lines=ragged,median_gap=float(np.median(gaps)),median_height=h)
  if ragged>=len(ls)*.5 and np.median(gaps)>.3*h:evidence.update(protected=True,reason='repeated_short_ragged_separate_rows')
 return evidence

def apply(image,blocks):
 out,records=v1_apply(image,blocks)
 for r in records:
  if not r['accepted']:continue
  a,b=r['indices'];ev=[entry_structure(image,blocks[i]) for i in [a,b]];r['entry_structure']=ev
  if any(e['protected'] for e in ev):
   if 'merge_prev' in blocks[b]:out[b]['merge_prev']=blocks[b]['merge_prev']
   else:out[b].pop('merge_prev',None)
   r.update(accepted=False,reason='independent_entry_structure')
 return out,records
