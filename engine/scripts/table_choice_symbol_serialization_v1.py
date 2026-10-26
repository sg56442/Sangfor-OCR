#!/usr/bin/env python3
"""Serialize repeated textual choice fields without changing their symbols.

Plain HTML cells must contain two or more symbol-labelled textual alternatives,
and the same ordered labels must recur in a different cell of the table. This
is a representation-only diagnostic, with no page identities or score inputs.
"""
import collections
import re

TABLE = re.compile(r'<table\b[^>]*>.*?</table>', re.S | re.I)
CELL = re.compile(r'(<(?:td|th)\b[^>]*>)(.*?)(</(?:td|th)>)', re.S | re.I)
MAP = {'□': 'square', '■': 'blacksquare', '√': 'surd', '✓': 'checkmark'}
MARKER = re.compile('[' + ''.join(MAP) + ']')
LABEL = re.compile(r'[A-Za-z\u3400-\u9fff][A-Za-z\u3400-\u9fff \t]{0,23}')


def choice_labels(value):
    if any(c in value for c in '$\\<&'):
        return None
    marks = list(MARKER.finditer(value))
    if not 2 <= len(marks) <= 8 or value[:marks[0].start()].strip():
        return None
    labels = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(value)
        label = value[mark.end():end].strip()
        if not LABEL.fullmatch(label):
            return None
        labels.append(label)
    if len(set(labels)) != len(labels):
        return None
    return tuple(labels)


def transform(markup):
    changes = []
    def table(match):
        original = match[0]
        signatures = collections.Counter(choice_labels(m[2]) for m in CELL.finditer(original))
        def cell(m):
            labels = choice_labels(m[2])
            if labels is None or signatures[labels] < 2:
                return m[0]
            after = ''.join('$\\' + MAP[c] + '$' if c in MAP else c for c in m[2])
            back = after
            for symbol, macro in MAP.items():
                back = back.replace('$\\' + macro + '$', symbol)
            assert back == m[2]
            changes.append(dict(before=m[2], after=after, ordered_text_labels=labels,
                                repeated_choice_fields=signatures[labels],
                                exact_symbol_and_text_roundtrip=True))
            return m[1] + after + m[3]
        return CELL.sub(cell, original)
    return TABLE.sub(table, markup), changes
