"""Shared production/replay argv: accepted strict-prime v4, every old gate retained."""
from pathlib import Path
R=Path(__file__).resolve().parents[2]
def column_command(native,pages,combined,columns,answers,out):
 return ['/opt/p2t10/venv/bin/python','-B',str(R/'code/experimenter/compose_table_columns_prime_v4.py'),'--native',str(native),'--pages',str(pages),'--combined',str(combined),'--columns',str(columns),'--answers',str(answers),'--out',str(out),'--consolidation']
