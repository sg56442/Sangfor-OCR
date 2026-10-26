"""Zero-call pure-rule runner. All/base from audited native; tail also accepts audited v2 pure B.
Rules run once, in declared order. No scoring, learned detector or cached aux input.
"""
import argparse,copy,hashlib,json,os,sys,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
GT=['/opt/p2t10/hidden/OmniDocBench.json','/opt/p2t10/hidden/source_validation_v2_references.jsonl','/opt/p2t10/hidden/source_validation_v1_references.jsonl']
BASE=['typed','fraction','canonical','fonts','aliases','formula-boundary','single-atom-vector']
TAIL=['math-whitespace','inline-delimiters','paragraph-v6','choice','numeric-v2-equality','finalcurrency']
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2));t.replace(p)
def dependencies():
 sys.path[:0]=[str(ROOT/'code/research'),str(ROOT/'code/runtime'),str(ROOT/'scripts')]
 import single_model_a_rules_v1 as s
 import audit_single_model_inputs_v1
 files={Path(__file__).resolve(),ROOT/'scripts/table_numeric_equality_v1.py'}
 for m in list(sys.modules.values()):
  p=getattr(m,'__file__',None)
  if p and Path(p).suffix=='.py' and (Path(p).resolve().is_relative_to(ROOT) or 'mineru_vl_utils' in p):files.add(Path(p).resolve())
 assert not any('rapidocr' in str(p).lower() or 'teleocr' in str(p).lower() for p in files)
 return s,{str(p):sha(p) for p in sorted(files)}
def apply_stage(s,name,image,raw):
 b=raw['blocks'];trace=[]
 if name=='typed':raw['blocks'],trace,_=s.typed(image,b)
 elif name=='fraction':raw['blocks'],trace,_=s.apply_fraction(image,b)
 elif name=='paragraph-v6':raw['blocks'],trace=s.paragraph(image,b)
 else:
  funcs={'canonical':lambda x:s.canonical.transform(x,'canonical'),'fonts':lambda x:s.fonts.transform(x,'fonts'),'aliases':lambda x:s.fonts.transform(x,'aliases'),'formula-boundary':s.boundary.repair,'single-atom-vector':s.vector.convert,'math-whitespace':s.whitespace,'inline-delimiters':s.delimiters,'choice':s.choice,'numeric-v2-equality':s.numeric}
  for i,block in enumerate(b):
   target='equation' if name in ['formula-boundary','single-atom-vector'] else 'table'
   if block['type']!=target:continue
   before=block.get('content','');after,record=funcs[name](before)
   if after!=before:trace.append(dict(index=i,before=before,after=after,detail=record));block['content']=after
 return trace

def main():
 p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--pages',required=True);p.add_argument('--out');p.add_argument('--profile',choices=['all','base','tail'],default='all');p.add_argument('--combined','--combined-tail',dest='combined');p.add_argument('--verify-native',action='store_true');p.add_argument('--freeze');p.add_argument('--write-freeze');p.add_argument('--smoke-first',type=int);p.add_argument('--_hidden',action='store_true',help=argparse.SUPPRESS);a=p.parse_args()
 if not a._hidden:
  paths=[x for x in GT if Path(x).exists()];shell='set -euo pipefail\nn="$1"; shift\nfor ((i=0;i<n;i++)); do mount --bind /dev/null "$1"; test ! -s "$1"; shift; done\nexec "$@"'
  cmd=['unshare','--mount','--propagation','private','/bin/bash','-c',shell,'track-a-hidden',str(len(paths)),*paths,sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--_hidden']
  raise SystemExit(subprocess.run(cmd,env=dict(os.environ,OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1')).returncode)
 assert all(not Path(x).exists() or Path(x).stat().st_size==0 for x in GT),'GT not hidden'
 s,closure=dependencies()
 if a.write_freeze:
  dest=Path(a.write_freeze).resolve();assert dest.is_relative_to(ROOT) and not dest.exists();save(dest,dict(source_hashes=closure,base=BASE,tail=TAIL,extra_calls=0,native_protocol_audit_sha256=sha(ROOT/'reports/rsi_single_model_native_inputs_v1.json')));return
 assert a.freeze and a.out
 frozen=load(a.freeze);assert closure==frozen['source_hashes'] and frozen['base']==BASE and frozen['tail']==TAIL
 native=Path(a.native).resolve();pages=Path(a.pages).resolve();out=Path(a.out).resolve();auditpath=ROOT/'reports/rsi_single_model_native_inputs_v1.json';audit=load(auditpath);assert sha(auditpath)==frozen['native_protocol_audit_sha256']
 manifest=load(pages);ids={x['id'] for x in manifest};assert len(manifest)==len(ids)==1651
 matches=[x for x in audit['runs'].values() if (ROOT/x['native']).resolve()==native]
 if a.verify_native or not matches:
  from audit_single_model_inputs_v1 import audit as verify_native
  binding=verify_native(native,ids)
  expected={json.dumps(g['parameters'],sort_keys=True) for g in audit['runs']['initial']['sampling_parameter_groups']}
  assert {json.dumps(g['parameters'],sort_keys=True) for g in binding['sampling_parameter_groups']}==expected,'Native sampling changed'
 else:
  assert len(matches)==1;binding=matches[0]
 binding_sha=hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest()
 assert sha(native/'predictions/worker_receipt.json')==binding['receipt_sha256'];assert sha(native/'predictions/route_trace.jsonl')==binding['trace_sha256'];assert sha(native/'audit/http.jsonl')==binding['http_sha256'];assert sha(pages)==audit['pages_sha256']
 manifest=load(pages);assert len(manifest)==1651;ids={x['id'] for x in manifest};assert len(ids)==1651
 stages=BASE+TAIL if a.profile=='all' else BASE if a.profile=='base' else TAIL
 source=native/'predictions';prior_order=[];parent_hashes={}
 if a.combined:
  assert a.profile=='tail';combined=Path(a.combined).resolve();source=combined/'predictions';cr=load(combined/'composition_receipt.json');assert cr['status']=='COMPLETE';prior_order=cr.get('order',[]);assert not set(stages)&set(cr.get('rule_stages',[])),'Repeated tail forbidden'
  if cr.get('track')=='A':
   assert cr['profile']=='base' and cr['native']==str(native) and cr['native_audit_sha256']==sha(auditpath)
   assert cr['source_hashes']==closure
  else:
   pipeline=combined.parent/'pipeline.json';st=load(pipeline);assert st['status']=='COMPLETE' and st['native_run']==str(native) and st['input_manifest_sha256']==sha(pages)
   allowed={'native','ae_build','ae_recognize','g_prepare','g_recognize','g_recognize_processor','g_boundary_recognize','g_boundary_recognize_processor','aecg_compose','e_prepare','e_recognize','e_recognize_processor','e_apply','e_compose','columns_prepare','columns_recognize','columns_processor','columns_compose','m_compose','layout_prepare','group_recognize','group_processor','rowpair_recognize','rowpair_processor','layout_compose','representation_compose','score'}
   assert st['steps'] and all(z['name'] in allowed and z['returncode']==0 for z in st['steps']);assert st.get('table_columns') in ['none','source','source+consolidation'];assert st['runtime_GT'] is False
   assert all(sha(ROOT/f)==h for f,h in st['source_hashes'].items());assert not any(any(t in f.lower() for t in ['aux0016','rapidocr','teleocr']) for f in st['source_hashes'])
   assert prior_order and set(prior_order)<= {'AE','TYPED_SOURCE_GUARD','C','G','E','source_columns_v4','native_column_consolidation_v2','TABLE_MATH_CANONICAL','local_group_v1','rowpair_v1','fonts','aliases','formula-boundary','single-atom-vector'}
   parent_hashes[str(pipeline)]=sha(pipeline)
  parent_hashes[str(combined/'composition_receipt.json')]=sha(combined/'composition_receipt.json')
 for sub,ext in [('raw','json'),('markdown','md')]:assert {f.stem for f in (source/sub).glob('*.'+ext)}==ids
 assert out.is_relative_to(ROOT) and not out.exists();out.mkdir(parents=True)
 save(out/'native_binding.json',binding)
 for sub in ['predictions/raw','predictions/markdown','provenance']:(out/sub).mkdir(parents=True)
 start=time.time();counts={name:dict(changed_pages=0,seconds=0.) for name in stages};changes=[];selected=manifest[:a.smoke_first] if a.smoke_first else manifest
 assert a.smoke_first is None or 0<a.smoke_first<=len(manifest)
 for row in selected:
  pid=row['id'];nr=native/'predictions/raw'/(pid+'.json');nm=native/'predictions/markdown'/(pid+'.md');assert sha(nr)==binding['predictions_sha256'][pid]['raw'] and sha(nm)==binding['predictions_sha256'][pid]['markdown']
  rp=source/'raw'/nr.name;mp=source/'markdown'/nm.name;raw=load(rp);original=copy.deepcopy(raw);before_md=mp.read_text();assert s.json2md(raw['blocks'])==before_md
  if a.combined:
   prov=load(Path(a.combined)/'provenance'/nr.name);assert prov['candidate_raw_sha256']==sha(rp) and prov['candidate_markdown_sha256']==sha(mp);assert prov['native_raw_sha256']==sha(nr) and prov['image_sha256']==sha(row['image'])
  records={}
  with s.Image.open(row['image']) as im:
   im=im.convert('RGB')
   for stage in stages:
    now=time.time();before=copy.deepcopy(raw)
    if stage=='finalcurrency':
     plain=s.json2md(raw['blocks']);md,trace=s.serialize_markdown(plain);changed=md!=plain
    else:trace=apply_stage(s,stage,im,raw);changed=raw!=before
    counts[stage]['seconds']+=time.time()-now;counts[stage]['changed_pages']+=int(changed);records[stage]=trace
  if 'finalcurrency' not in stages:md=s.json2md(raw['blocks'])
  dst=out/'predictions/raw'/nr.name;dm=out/'predictions/markdown'/nm.name;save(dst,raw);dm.write_text(md)
  changed=raw!=original or md!=before_md
  if changed:changes.append(pid)
  save(out/'provenance'/nr.name,dict(native_raw_sha256=sha(nr),native_markdown_sha256=sha(nm),input_raw_sha256=sha(rp),input_markdown_sha256=sha(mp),candidate_raw_sha256=sha(dst),candidate_markdown_sha256=sha(dm),image_sha256=sha(row['image']),rules=records,extra_calls=0))
 assert closure=={f:sha(f) for f in closure};assert all(sha(p)==h for p,h in parent_hashes.items())
 save(out/'composition_receipt.json',dict(status='COMPLETE',track='A' if not a.combined else 'PURE_RULE_TAIL',profile=a.profile,native=str(native),source=str(source),native_audit_sha256=sha(auditpath),native_binding_sha256=binding_sha,native_binding_file_sha256=sha(out/'native_binding.json'),native_verification='runtime' if a.verify_native or not matches else 'historical_audit_hash_bound',native_receipt_sha256=sha(native/'predictions/worker_receipt.json'),input_manifest_sha256=sha(pages),source_hashes=closure,parent_hashes=parent_hashes,order=prior_order+stages,rule_stages=stages,counts=dict(pages=len(selected),changed_pages=len(changes)),stage_counts=counts,changed_pages=changes,extra_calls=0,model_calls=0,DB_calls=0,extra_prompt_tokens=0,extra_completion_tokens=0,runtime_GT=False,GT_hidden=True,seconds=time.time()-start,smoke=bool(a.smoke_first),scored=False))
 print(json.dumps(dict(pages=len(selected),changed_pages=len(changes),seconds=time.time()-start)),flush=True)
if __name__=='__main__':main()
