#!/usr/bin/env python3
"""Encode literal currency after native paragraph assembly, preserving merges."""
import re

from literal_currency_html_v1 import encode


def serialize_markdown(markdown):
    pieces = re.split(r'(\n[ \t]*\n)', markdown)
    edits = []
    for index in range(0, len(pieces), 2):
        before = pieces[index]
        after, changes = encode(before)
        if changes:
            pieces[index] = after
            edits.append(dict(paragraph_index=index // 2, before=before, after=after, changes=changes))
    return ''.join(pieces), edits
