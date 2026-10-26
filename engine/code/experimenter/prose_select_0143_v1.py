"""Scoped insertion/replacement from current geometric proposals; preserves other bytes."""
import json,sys,os,argparse
from pathlib import Path
from prose_geometry_0143_v1 import contains,subsequence,intersection,significant
from brace_compose_0136_v4 import spans

def edit(rb,md,q,answer,strict=True):
 if answer.get('finish')!='stop':raise ValueError('incomplete response')
 raw=json.loads(rb);bs=raw['blocks'];sp=spans(rb);text=answer['text'];box=q['source_bbox']
 if not text.strip() or '\x00' in text:raise ValueError('empty/control response')
 ids=q['replace_owners'];nl='\r\n' if '\r\n' in md else '\n';text=text.replace('\r\n','\n').replace('\n',nl)
 if ids:
  if len(ids)!=1:raise ValueError('ambiguous target')
  i=ids[0];old=bs[i];content=old.get('content')
  if old['type']!='text' or not content or not contains(box,old['bbox']):raise ValueError('invalid ownership')
  if strict and not subsequence(content,text):raise ValueError('native character conservation')
  if md.count(content)!=1:raise ValueError('nonunique MD anchor')
  lo=md.index(content);hi=lo+len(content);a,b=sp[i];new=dict(old,content=text,bbox=box);segment=json.dumps(new,ensure_ascii=False)
  nr=rb[:a]+segment+rb[b:];nm=md[:lo]+text+md[hi:]
  assert nr[:a]+rb[a:b]+nr[a+len(segment):]==rb and nm[:lo]+content+nm[lo+len(text):]==md
 else:
  i=q['insert_before'];old=bs[i];content=old.get('content')
  if not content or md.count(content)!=1:raise ValueError('nonunique insertion anchor')
  if strict and any(significant(box,b['bbox']) and b['type'] not in ['title'] for b in bs):raise ValueError('unowned group overlaps native')
  lo=md.index(content);a=sp[i][0];new=dict(type='text',bbox=box,angle=0,content=text,merge_prev=False);segment=json.dumps(new,ensure_ascii=False)+',';ins=text+nl+nl;nr=rb[:a]+segment+rb[a:];nm=md[:lo]+ins+md[lo:]
  assert nr[:a]+nr[a+len(segment):]==rb and nm[:lo]+nm[lo+len(ins):]==md
 return nr,nm,dict(target=ids,insert_before=q['insert_before'],text=text,original_target=[bs[i] for i in ids],non_target_bytes_preserved=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();O=Path(a.run).resolve();cfg=json.loads((O/'runtime_inputs.json').read_text());base=Path(cfg['inputs']);qs=json.loads((O/'prepared.json').read_text());ans={v['ordinal']:v for v in json.loads((O/'responses.json').read_text())};records=[]
 for variant in ['generator','selected']:
  dest=O/(variant+'_v3_predictions');changes={}
  for q in qs:changes.setdefault(q['raw'],[]).append(q)
  for sub in ['raw','markdown']:
   (dest/sub).mkdir(parents=True,exist_ok=True)
   for f in (base/sub).iterdir():
    if f.is_file() and not (dest/sub/f.name).exists():os.link(f.resolve(),dest/sub/f.name)
  for path,rows in changes.items():
   p=Path(path);rb=p.read_bytes().decode();md=(base/'markdown'/(p.stem+'.md')).read_bytes().decode()
   # Descending original indices keep all subsequent original offsets/owners stable.
   for q in sorted(rows,key=lambda q:(q['replace_owners'] or [q['insert_before']])[0],reverse=True):
    try:rb,md,rec=edit(rb,md,q,ans[q['ordinal']],variant=='selected');rec.update(accepted=True)
    except (ValueError,AssertionError,KeyError,IndexError) as e:rec=dict(accepted=False,reason=str(e))
    records.append(dict(variant=variant,ordinal=q['ordinal'],**rec))
   for sub,ext,data in [('raw','json',rb),('markdown','md',md)]:
    f=dest/sub/(p.stem+'.'+ext);tmp=f.with_suffix('.tmp');tmp.write_bytes(data.encode());tmp.replace(f)
 (O/'compose_v3.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));print(json.dumps(records,ensure_ascii=False))
if __name__=='__main__':main()
