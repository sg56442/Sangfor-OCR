"""Track A: deterministic rules only. No model/DB/network/cached candidates.
Input must be raw native, not a mixed combined stage. CLI verifies RSI native audit.
"""
import sys,copy,json,argparse,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'code/research'),str(ROOT/'code/runtime'),str(ROOT/'scripts')]
from PIL import Image
from mineru_vl_utils.post_process import json2md
from typed_grid_source_guard import apply as typed
from runtime_aec_api import apply_fraction
from column_continuation_v6 import apply as paragraph
import probe_table_math_canonical as canonical
import probe_table_math_fonts as fonts
import probe_formula_boundary_group as boundary
import single_atom_vector_v1 as vector
from table_math_whitespace_v1 import transform as whitespace
from table_inline_delimiters_v1 import transform as delimiters
from table_choice_symbol_serialization_v1 import transform as choice
from numeric_uniform_package_v2 import transform as numeric
from literal_currency_serializer_v2 import serialize_markdown

def apply(image,raw):
 out=copy.deepcopy(raw);b,t,c=typed(image,out['blocks']);b,f,c=apply_fraction(image,b);records={'typed':t,'fraction':f,'representation':[]}
 for i,block in enumerate(b):
  text=block.get('content','')
  ops=[]
  if block['type']=='table':ops=[('canonical',lambda s:canonical.transform(s,'canonical')),('fonts',lambda s:fonts.transform(s,'fonts')),('aliases',lambda s:fonts.transform(s,'aliases')),('whitespace',whitespace),('delimiters',delimiters),('choice',choice),('numeric',numeric)]
  elif block['type']=='equation':ops=[('formula-boundary',boundary.repair),('single-atom-vector',vector.convert)]
  for name,fn in ops:
   after,trace=fn(text)
   if after!=text:records['representation'].append(dict(index=i,rule=name,before=text,after=after,trace=trace))
   text=after
  if ops:block['content']=text
 b,p=paragraph(image,b);records['paragraph']=p;out['blocks']=b
 md,trace=serialize_markdown(json2md(b));records['currency']=trace
 return out,md,records

def main():
 p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--pages',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();native=Path(a.native).resolve();pages=Path(a.pages).resolve();out=Path(a.out).resolve();audit=json.loads((ROOT/'reports/rsi_single_model_native_inputs_v1.json').read_text());matches=[x for x in audit['runs'].values() if (ROOT/x['native']).resolve()==native];assert len(matches)==1
 rec=native/'predictions/worker_receipt.json';assert sha(rec)==matches[0]['receipt_sha256'];assert sha(pages)==audit['pages_sha256'];manifest=json.loads(pages.read_text());assert len(manifest)==1651
 assert out.is_relative_to(ROOT) and not out.exists();out.mkdir(parents=True)
 for sub in ['predictions/raw','predictions/markdown','provenance']:(out/sub).mkdir(parents=True)
 start=time.time();changed=[]
 for row in manifest:
  name=row['id'];rp=native/'predictions/raw'/(name+'.json');mp=native/'predictions/markdown'/(name+'.md');raw=json.loads(rp.read_text());assert json2md(raw['blocks'])==mp.read_text()
  with Image.open(row['image']) as im:result,md,trace=apply(im.convert('RGB'),raw)
  dest=out/'predictions/raw'/rp.name;dest.write_text(json.dumps(result,ensure_ascii=False,indent=2));dm=out/'predictions/markdown'/mp.name;dm.write_text(md)
  if result!=raw or md!=mp.read_text():changed.append(name)
  prov=dict(native_raw_sha256=sha(rp),native_markdown_sha256=sha(mp),candidate_raw_sha256=sha(dest),candidate_markdown_sha256=sha(dm),image_sha256=sha(row['image']),rules=trace)
  (out/'provenance'/rp.name).write_text(json.dumps(prov,ensure_ascii=False,indent=2))
 (out/'composition_receipt.json').write_text(json.dumps(dict(status='COMPLETE',track='A',native=str(native),pages=1651,changed_pages=changed,model_calls=0,DB_calls=0,runtime_GT=False,seconds=time.time()-start,scope='new pure rule composition; score unmeasured'),indent=2))
if __name__=='__main__':main()
