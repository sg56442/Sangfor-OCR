"""Fixed operator-closed uncertainty then legacy equality package; representation only."""
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
def _module(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
import table_numeric_uncertainty_v2 as U
E=_module('table_numeric_equality_v1')
def transform(markup):
 middle,u=U.transform(markup);after,e=E.transform(middle)
 return after,dict(uncertainty=u,equality=e)
