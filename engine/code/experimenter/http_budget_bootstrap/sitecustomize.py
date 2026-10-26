import os,sys
if os.environ.get('FT1021_SUPPLEMENTAL_BUDGET'):
 try:
  from pathlib import Path
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
  from http_budget_v1 import install
  install()
 except BaseException:
  # Python normally ignores sitecustomize errors; explicitly fail closed.
  os._exit(72)
