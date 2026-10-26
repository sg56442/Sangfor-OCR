"""Batch G inputs from caller-supplied current native predictions. No GT/source identity routing."""
import argparse,pathlib,json,shutil,hashlib
from g_v4.prepare import prepare
R=pathlib.Path(__file__).resolve().parents[2];p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--pages',required=True);p.add_argument('--native-audit',required=True);p.add_argument('--out',required=True);a=p.parse_args();out=pathlib.Path(a.out).resolve();assert out.is_relative_to(R);out.mkdir(parents=True,exist_ok=False);native=pathlib.Path(a.native);pages=json.load(open(a.pages));audit=pathlib.Path(a.native_audit);assert audit.exists();base=out/'baseline';(base/'predictions/raw').mkdir(parents=True);(base/'predictions/markdown').mkdir();probe=out/'probe';probe.mkdir();props=[];reqs=[];sources=[]
for page in pages:
 pid=page['id'];rawpath=native/'raw'/f'{pid}.json';md=native/'markdown'/f'{pid}.md';raw=json.load(open(rawpath));shutil.copyfile(rawpath,base/'predictions/raw'/rawpath.name);shutil.copyfile(md,base/'predictions/markdown'/md.name);local_props,local_reqs=prepare(page['image'],raw['blocks'],probe/'page_crops'/pid);offset=len(props)
 for x in local_props:x.update(proposal_id=x['proposal_id']+offset,page=pid,page_image=page['image']);props.append(x)
 for x in local_reqs:x['proposal']+=offset;reqs.append(x)
 sources.append({'page_diagnostic_only':pid,'raw_sha256':hashlib.sha256(rawpath.read_bytes()).hexdigest(),'markdown_sha256':hashlib.sha256(md.read_bytes()).hexdigest()})
(base/'pages.json').write_text(json.dumps(pages,indent=2))
for name,obj in [('proposals',props),('requests',reqs),('preparation',{'family':'G','variant':'G_SOURCE_GRAMMAR_V4_CURRENT_RUN','input_pages':len(pages),'eligible_before_budget':len(props),'positive':sum(p['triggered'] for p in props),'normal_controls':sum(p['normal_control'] for p in props),'requests':len(reqs),'selected':0,'caller_native':str(native.resolve()),'caller_native_http':str(audit.resolve()),'no_fixed_historical_prediction_import':True,'runtime_gt':False}),('current_native_identity',sources)]:(probe/(name+'.json')).write_text(json.dumps(obj,indent=2))
print((probe/'preparation.json').read_text())
