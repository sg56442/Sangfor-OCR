#!/usr/bin/env python3
"""Equivalent table math normalization: font-argument groups or bracket aliases.

Characters, font commands, scripts and operators are preserved. This diagnoses
serialization effects, not OCR character recovery. Unknown syntax falls back.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from pylatexenc.latexwalker import LatexWalker, LatexMacroNode
from probe_table_math_canonical import CELL, INLINE

ROOT = Path(__file__).resolve().parents[1]
FONTS = {'mathrm', 'mathbf', 'mathsf', 'mathtt', 'mathit', 'mathnormal', 'mathcal', 'mathbb', 'mathfrak'}
TEXT = {'text', 'textrm', 'textsf', 'texttt', 'textnormal', 'verb', 'url', 'href', 'string'}
ALIASES = {'lbrack': '[', 'rbrack': ']', 'lbrace': r'\{', 'rbrace': r'\}'}


def simplify(expression, variant):
    try:
        nodes, pos, length = LatexWalker(expression, tolerant_parsing=False).get_latex_nodes()
        assert pos == 0 and length == len(expression)
    except Exception:
        return expression
    edits = []

    def visit(items):
        for node in items or []:
            if isinstance(node, LatexMacroNode):
                if node.macroname in TEXT:
                    continue
                arguments = getattr(node.nodeargd, 'argnlist', []) or []
                if variant == 'fonts' and node.macroname in FONTS and len(arguments) == 1:
                    arg = arguments[0]
                    if arg is not None and getattr(arg, 'delimiters', None) == ('{', '}'):
                        value = expression[arg.pos+1:arg.pos+arg.len-1]
                        nested = value.strip()
                        count = 0
                        while nested.startswith('{') and nested.endswith('}'):
                            nested = nested[1:-1].strip()
                            count += 1
                        if count and re.fullmatch(r'[A-Za-z0-9]+', nested):
                            edits.append((arg.pos+1, arg.pos+arg.len-1, nested))
                            continue
                if variant == 'aliases' and node.macroname in ALIASES:
                    edits.append((node.pos, node.pos+node.len, ALIASES[node.macroname]))
                for arg in arguments:
                    visit(getattr(arg, 'nodelist', None))
            else:
                visit(getattr(node, 'nodelist', None))
    visit(nodes)
    for a, b, replacement in sorted(edits, reverse=True):
        expression = expression[:a] + replacement + expression[b:]
    return expression


def transform(markdown, variant):
    changes = []
    def cell(match):
        def formula(m):
            after = simplify(m[1], variant)
            if after != m[1]:
                changes.append(dict(before=m[1], after=after))
            return r'\(' + after + r'\)'
        return match[1] + INLINE.sub(formula, match[2]) + match[3]
    return CELL.sub(cell, markdown), changes


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--combined', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    source, out = Path(a.combined).resolve(), Path(a.out).resolve()
    assert out.is_relative_to(ROOT)
    out.mkdir(parents=True, exist_ok=False)
    # Critical argument and text boundaries, independently of score outcomes.
    assert simplify(r'\mathrm{{Cu}}_{2}', 'fonts') == r'\mathrm{Cu}_{2}'
    assert simplify(r'\frac{\mathrm{{Na}}}{x}', 'fonts') == r'\frac{\mathrm{Na}}{x}'
    for text in [r'\text{\mathrm{{Cu}}}', r'\mathrm{A+B}', r'\mathrm{A{B}}', r'{ab}^2']:
        assert simplify(text, 'fonts') == text
    assert simplify(r'\left\lbrack x\right\rbrack', 'aliases') == r'\left[x\right]'
    receipts = {}
    for variant in ['fonts', 'aliases']:
        dest = out / variant
        dest.mkdir()
        edits = []
        for path in sorted((source / 'predictions/markdown').glob('*.md')):
            before = path.read_text()
            after, changes = transform(before, variant)
            assert transform(after, variant)[0] == after, 'Not idempotent'
            if after != before:
                (dest / path.name).write_text(after)
                edits.append(dict(page_locator=path.stem, source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), changes=changes))
        receipts[variant] = dict(changed_pages=len(edits), changed_formulas=sum(len(x['changes']) for x in edits), edits=edits)
    receipt = dict(source=str(source), source_pages=len(list((source / 'predictions/markdown').glob('*.md'))),
                   variants=receipts, runtime_GT=False, new_model_calls=0, representation_only=True,
                   source_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out / 'preparation.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: {a: b for a, b in v.items() if a != 'edits'} for k, v in receipts.items()}))


if __name__ == '__main__':
    main()
