"""Only re-read source columns when native and physical column counts disagree.

Both counts use the current input. This conservative gate may miss row-only
errors; it never uses a page name, score, GT, or historical answer.
"""
from source_column_runtime_v4 import apply_source_columns
from source_column_runtime_v4 import propose_source_columns as propose_all
from table_mechanisms import grids


def discrepancy(raw, proposal):
    parsed = grids(raw['blocks'][proposal['block_index']].get('content', ''))
    if len(parsed) != 1:
        return False
    native_width = parsed[0]['width']
    source_width = len(proposal['inputs'])
    return native_width > 0 and source_width > 0 and native_width != source_width


def propose_source_columns(image, native_raw):
    return [p for p in propose_all(image, native_raw) if discrepancy(native_raw, p)]
