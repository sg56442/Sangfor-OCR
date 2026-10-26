#!/usr/bin/env python3
"""Fixed equivalent-operator closure: ASCII decimals and TeX pm/mp or Unicode ±/∓.

Only a complete existing inline formula of the form decimal +/- decimal is
eligible. Decimal strings are exact; equivalent operator spellings map to TeX; each
operator remains math. Signed values, units, scripts and compound expressions
are deliberately outside this representation rule's grammar.
"""
import re

CELL = re.compile(r'(<(?:td|th)\b[^>]*>)(.*?)(</(?:td|th)>)', re.S | re.I)
INLINE = re.compile(r'(?<![\\$])\$(?!\$)(.*?)(?<!\\)\$(?!\$)', re.S)
DECIMAL = r'(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)'
UNCERTAINTY = re.compile(r'\s*(' + DECIMAL + r')\s*(\\(?:pm|mp)|±|∓)\s*(' + DECIMAL + r')\s*')


def transform(markup):
    changes = []
    def cell(match):
        def formula(m):
            parsed = UNCERTAINTY.fullmatch(m[1])
            if parsed is None:
                return m[0]
            left, original_operator, right = parsed.groups()
            operator = {"±": r"\pm", "∓": r"\mp"}.get(original_operator, original_operator)
            after = left + '$' + operator + '$' + right
            assert re.sub(r'\s+', '', m[1]) == left + original_operator + right
            changes.append(dict(before=m[0], after=after,
                                decimal_strings=[left, right], operator=operator, original_operator=original_operator,
                                numeric_lexemes_and_operator_preserved=True))
            return after
        return match[1] + INLINE.sub(formula, match[2]) + match[3]
    return CELL.sub(cell, markup), changes
