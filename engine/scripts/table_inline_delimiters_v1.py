#!/usr/bin/env python3
"""Use one conventional inline-math delimiter inside HTML table cells.

Only delimiter spelling changes; formula bodies, cell topology, text and
literal currency stay unchanged. This is serialization, not OCR correction.
"""
import re

CELL=re.compile(r'(<(?:td|th)\b[^>]*>)(.*?)(</(?:td|th)>)',re.S|re.I)
INLINE=re.compile(r'(?<!\\)\\\((.*?)\\\)',re.S)


def transform(markup):
    changes=[]
    def cell(m):
        def inline(q):
            body=q.group(1)
            if '$' in body or r'\(' in body or not body.strip():return q.group(0)
            changes.append(dict(before=q.group(0),after='$'+body+'$',body_unchanged=True))
            return '$'+body+'$'
        return m.group(1)+INLINE.sub(inline,m.group(2))+m.group(3)
    return CELL.sub(cell,markup),changes
