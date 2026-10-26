"""Byte-splice full transcripts; original bytes recoverable by removing recorded insertions."""
import json,sys,os,re,hashlib
from pathlib import Path
from brace_production_0136_v1 import anchor,coverage

def spans(s):
 sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
 from phase2_array_label_runtime_v1 import block_spans
 rb=s.encode();mapping=block_spans(rb,json.loads(s))
 return [(len(rb[:mapping[i][0]].decode()),len(rb[:mapping[i][1]].decode())) for i in range(len(mapping))]

def select(text,finish,blocks,i):
 if finish!='stop' or not text.strip():return False,'incomplete_or_empty'
 if coverage(blocks,i):return False,'native_overlap'
 if any(x in text for x in ['```','<html','<table','![','\ufffd']):return False,'unexplained_format'
 lines=[x.strip() for x in text.splitlines() if x.strip()]
 # Repeated full rows remain in generator. Repetition cannot be blessed from a known answer.
 # Repeated complete rows are retained; equality alone is not a source-damage signal.
 nearby=[b.get('content') for b in blocks[max(0,i-1):i]+blocks[i+1:i+2] if b.get('content')]
 if any(text.strip() in t or t.strip()==text.strip() for t in nearby):return False,'adjacent_native_coverage'
 return True,'finite_support_no_duplicate_or_format_conflict'
def main():
 O=Path(sys.argv[1]);base=Path(json.loads((O/'runtime_inputs.json').read_text())['inputs']);responses={q['ordinal']:q for q in json.loads((O/'responses.json').read_text())};records=[]
 for variant in ['generator','selected']:
  dest=O/(variant+'_predictions')
  for sub in ['raw','markdown']:
   (dest/sub).mkdir(parents=True,exist_ok=True)
   for p in (base/sub).iterdir():
    if p.is_file() and not (dest/sub/p.name).exists():os.link(p.resolve(),dest/sub/p.name)
  grouped={}
  for q in json.loads((O/'prepared.json').read_text()):grouped.setdefault(q['raw'],[]).append(q)
  for name,qs in grouped.items():
   src=Path(name);s=src.read_bytes().decode();raw=json.loads(s);blocks=raw['blocks'];
   try:ss=spans(s)
   except (AssertionError,KeyError,ValueError,IndexError) as error:
    records.append(dict(variant=variant,applied=False,selected=False,reason='ambiguous_top_level_JSON_binding',detail=str(error)));continue
   md=(base/'markdown'/(src.stem+'.md')).read_bytes().decode();ri=[];mi=[]
   for q in sorted(qs,key=lambda q:q['owner']):
    a=responses.get(q['ordinal'],{});i=q['owner'];text=a.get('text','');accept,reason=select(text,a.get('finish'),blocks,i);at=anchor(blocks,i,md)
    applied=a.get('finish')=='stop' and bool(text.strip()) and at is not None and (variant=='generator' or accept)
    records.append(dict(variant=variant,ordinal=q['ordinal'],selected=variant=='selected' and applied,applied=applied,reason=reason,owner=i,source=q['source']))
    if not applied:continue
    nl='\r\n' if '\r\n' in md else '\n';new=text.replace('\r\n','\n').replace('\n',nl)
    b=dict(type='text',bbox=blocks[i]['bbox'],angle=0,content=text,merge_prev=False)
    ri.append((ss[i][1],','+json.dumps(b,ensure_ascii=False)));mi.append((at,new+nl+nl))
   def splice(orig,ins):
    result=orig
    for _,(at,v) in sorted(enumerate(ins),key=lambda q:(q[1][0],q[0]),reverse=True):result=result[:at]+v+result[at:]
    # Undo at shifted offsets; exact reconstruction, including CRLF/null/spacing.
    shift=0;rev=[]
    for at,v in sorted(ins,key=lambda q:q[0]):rev.append((at+shift,v));shift+=len(v)
    restored=result
    for at,v in reversed(rev):assert restored[at:at+len(v)]==v;restored=restored[:at]+restored[at+len(v):]
    assert restored==orig
    return result
   for sub,ext,old,ins in [('raw','json',s,ri),('markdown','md',md,mi)]:
    if not ins:continue
    result=splice(old,ins);p=dest/sub/(src.stem+'.'+ext);tmp=p.with_suffix('.tmp');tmp.write_bytes(result.encode());tmp.replace(p)
   if ri:assert len(json.loads(splice(s,ri))['blocks'])==len(blocks)+len(ri)
 (O/'compose.json').write_text(json.dumps(dict(records=records,exact_original_byte_reconstruction=True,all_original_owners_retained=True),indent=2))
if __name__=='__main__':main()
