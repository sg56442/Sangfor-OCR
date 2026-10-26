"""Current OCR columns only; no diagnostic labels or fixed row/column count."""
import re

def assemble(columns):
    lines=[[x.strip() for x in c.splitlines() if x.strip()] for c in columns]
    signatures=['Han' if len(re.findall('[\u4e00-\u9fff]',c))>len(re.findall('[A-Za-z]',c)) else 'Latin' for c in columns]
    period=next((k for k in range(2,len(columns)) if len(columns)%k==0 and len(set(signatures[:k]))>=2 and signatures==signatures[:k]*(len(columns)//k)),None)
    equal=bool(lines) and len({len(x) for x in lines})==1
    accepted=period is not None and equal
    content='\n'.join(' '.join(row) for start in range(0,len(lines),period) for row in zip(*lines[start:start+period])) if accepted else None
    return content,dict(signatures=signatures,minimal_repeating_period=period,same_line_count=equal,line_counts=[len(x) for x in lines],selected=accepted)
