"""Official cc1009 scorer, frozen markdown input and an explicit scoring-only GT subset."""
import argparse,json,pathlib,subprocess,time,hashlib
from score_receipts import component_entries
ROOT=pathlib.Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--predictions',required=True);p.add_argument('--out',required=True);p.add_argument('--cache');a=p.parse_args()
out=pathlib.Path(a.out).resolve();assert out.is_relative_to(ROOT);out.mkdir(parents=True,exist_ok=False)
pred=pathlib.Path(a.predictions).resolve();ids={x.stem for x in pred.glob('*.md')};assert ids
all_gt=json.load(open('/opt/p2t10/hidden/OmniDocBench.json'));gt=[x for x in all_gt if pathlib.Path(x['page_info']['image_path']).stem in ids];assert len(gt)==len(ids)
(out/'scoring_gt.json').write_text(json.dumps(gt,ensure_ascii=False))
cmd=['/opt/p2t10/venv/bin/python','/data/rh/code/omnidocbench-accelerated/run.py','--ground-truth',str(out/'scoring_gt.json'),'--predictions',str(pred),'--output',str(out/'evaluation'),'--cache',str(pathlib.Path(a.cache).resolve() if a.cache else out/'cdm_cache'),'--mode','accelerated']
if a.cache:assert pathlib.Path(a.cache).resolve().is_relative_to(ROOT)
start=time.time()
with (out/'launcher.log').open('w') as f:rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT).returncode
receipt=dict(returncode=rc,seconds=time.time()-start,input_pages=len(ids),expected_pages=len(gt),empty_markdown=sum(not x.read_text().strip() for x in pred.glob('*.md')),scorer='/data/rh/code/omnidocbench-accelerated/run.py',scorer_sha256=hashlib.sha256(pathlib.Path(cmd[1]).read_bytes()).hexdigest(),protocol='omnidoc-1651-c45-pb32-accelerated-v1',scope='full' if len(ids)==1651 else 'diagnostic_subset',gpu_seconds=0)
if rc==0:
 summary=json.load(open(out/'evaluation/score-summary.json'));receipt['summary']=summary
 receipt['official_stage_execution']=json.load(open(out/'evaluation/result/markdown_quick_match_run_summary.json'))['stage_execution']
 receipt['component_coverage']={k:dict(valid_pages=v['page_denominator'],excluded_or_not_applicable_pages=len(ids)-v['page_denominator'],missing_prediction_files=0) for k,v in summary['metrics'].items()}
 result=out/'evaluation/result'
 for label,name in [('text','markdown_quick_match_text_block_per_page_edit.json'),('formula','markdown_quick_match_display_formula_per_sample_CDM.json'),('table','markdown_quick_match_table_per_table_TEDS.json')]:
  key={'text':'text_block_Edit_dist','formula':'display_formula_CDM','table':'table_TEDS'}[label]
  try:
   item=component_entries(result,name,summary['metrics'][key]['page_denominator']);receipt[label+'_component_entries']=item['entries'];receipt[label+'_component_file_absent_not_applicable']=item['file_absent_not_applicable']
  except FileNotFoundError as error:
   receipt.update(official_returncode=rc,returncode=1,failure_class='LOCAL_RECEIPT_MISSING_APPLICABLE_COMPONENT',error=str(error));(out/'score_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));raise SystemExit(1)
(out/'score_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt));raise SystemExit(rc)
