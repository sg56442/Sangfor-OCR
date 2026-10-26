"""Strict Markdown paragraph binding for connective representation; no scientific gate change."""
from spacing_apply_0046 import span

def paragraph_span(md,old,new):
    start,end,replacement=span(md,old,new)
    assert start==0 or md[:start].endswith((b'\n\n',b'\r\n\r\n')), 'not_paragraph_start'
    assert not md[end:].strip() or md[end:].startswith((b'\n\n',b'\r\n\r\n')), 'not_paragraph_end'
    return start,end,replacement
