"""Local receipt helpers only; official scorer and aggregation are unchanged."""
import json,pathlib

def component_entries(result_dir,filename,official_valid_pages):
 path=pathlib.Path(result_dir)/filename
 if not path.exists():
  if official_valid_pages==0:return {'entries':0,'file_absent_not_applicable':True}
  raise FileNotFoundError(f'Applicable official component missing ({official_valid_pages} valid pages): {path}')
 return {'entries':len(json.loads(path.read_text())),'file_absent_not_applicable':False}
