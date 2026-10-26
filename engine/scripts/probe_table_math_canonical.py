#!/usr/bin/env python3
"""Frozen-output diagnostic of equivalent TeX script/group serialization.

This does not recover characters. Source expressions retain their symbols and
operators. Only math inside table cells is eligible; unknown syntax is retained.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from pylatexenc.latexwalker import LatexWalker, LatexGroupNode, LatexMacroNode

ROOT = Path(__file__).resolve().parents[1]
CELL = re.compile(r'(<(?:td|th)\b[^>]*>)(.*?)(</(?:td|th)>)', re.S | re.I)
INLINE = re.compile(r'\\\((.*?)\\\)', re.S)
SCRIPT = re.compile(r'(?<!\\)([_^])([A-Za-z0-9])')


def braces(expression):
    # Text/verb arguments are not math-script syntax. Reject ambiguous syntax
    # rather than rewriting an underscore that may be a literal identifier.
    try:
        nodes, _, _ = LatexWalker(expression, tolerant_parsing=False).get_latex_nodes()
    except Exception:
        return expression
    protected = []
    def visit(items):
        for node in items or []:
            if isinstance(node, LatexMacroNode):
                arguments = getattr(node.nodeargd, 'argnlist', []) or []
                if node.macroname in ['text', 'textrm', 'textsf', 'texttt', 'textnormal', 'verb', 'url']:
                    protected.append((node.pos, node.pos + node.len))
                else:
                    for argument in arguments:
                        visit(getattr(argument, 'nodelist', None))
            else:
                visit(getattr(node, 'nodelist', None))
    visit(nodes)
    return SCRIPT.sub(lambda m: m[0] if any(a <= m.start() < b for a,b in protected)
                      else m[1] + '{' + m[2] + '}', expression)


def ungroup(expression):
    # LatexWalker protects command arguments (including text/font scopes).
    # Only top-level scalar groups are removed. A preceding macro or script
    # is conservative exclusion, even if its argument schema is unavailable.
    try:
        nodes, pos, length = LatexWalker(expression, tolerant_parsing=False).get_latex_nodes()
        assert pos == 0 and length == len(expression)
    except Exception:
        return expression
    edits = []
    for i, node in enumerate(nodes):
        if not isinstance(node, LatexGroupNode) or node.delimiters != ('{', '}'):
            continue
        inner = expression[node.pos + 1:node.pos + node.len - 1]
        if not re.fullmatch(r'[A-Za-z]|[0-9]+', inner):
            continue
        prefix = expression[:node.pos].rstrip()
        suffix = expression[node.pos + node.len:].lstrip()
        if prefix.endswith(('_', '^')):
            continue
        if suffix.startswith(('_', '^')) and len(inner) > 1:
            continue
        previous = next((n for n in reversed(nodes[:i])
                         if expression[n.pos:n.pos + n.len].strip()), None)
        if isinstance(previous, LatexMacroNode):
            continue
        # Never modify a group adjacent to another explicit group, which
        # might be an unsupported macro argument sequence.
        if prefix.endswith('}') or suffix.startswith('{'):
            continue
        edits.append((node.pos, node.pos + node.len, inner))
    for start, end, replacement in reversed(edits):
        expression = expression[:start] + replacement + expression[end:]
    return expression


def transform(markdown, variant):
    changes = []
    def cell(match):
        def formula(m):
            result = braces(m[1]) if variant == 'braces' else braces(ungroup(m[1]))
            if result == m[1]:
                return m[0]
            changes.append({'before': m[1], 'after': result})
            return r'\(' + result + r'\)'
        return match[1] + INLINE.sub(formula, match[2]) + match[3]
    return CELL.sub(cell, markdown), changes


def checks():
    # Semantic boundaries: literal escaped underscores, macro arguments,
    # compound script bases and font scopes must survive normalization.
    assert braces(r'a\_b+x_1+y^2') == r'a\_b+x_{1}+y^{2}'
    assert braces(r'\text{path_name}_2') == r'\text{path_name}_{2}'
    assert ungroup(r'{S}_{1}^{h}={16},{000}') == r'S_{1}^{h}=16,000'
    for source in [r'\frac{1}{2}', r'\text{S}', r'\mathrm{S}',
                   r'{12}^2', r'{ab}^2', r'\unknown{x}', r'{\bf x}']:
        assert ungroup(source) == source, source
    outside = r'Ordinary x_1 and \(x_1\), <td>literal a\_b</td>'
    assert transform(outside, 'canonical')[0] == outside


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native', required=True)
    p.add_argument('--pages', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    checks()
    native, out = Path(a.native).resolve(), Path(a.out).resolve()
    assert out.is_relative_to(ROOT)
    out.mkdir(parents=True, exist_ok=False)
    pages = json.loads(Path(a.pages).read_text())
    receipt = {'scope': 'Exposed discovery frozen-output serialization; not character recovery',
               'runtime_GT': False, 'model_calls': 0,
               'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'semantic_boundary_checks': 'PASS', 'variants': {}}
    for variant in ['native', 'braces', 'canonical']:
        destination = out / variant
        destination.mkdir()
        edits = []
        for page in pages:
            source = native / (page['id'] + '.md')
            before = source.read_text()
            after, changes = (before, []) if variant == 'native' else transform(before, variant)
            (destination / source.name).write_text(after)
            if changes:
                edits.append({'page_locator': page['id'], 'changes': changes,
                              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
        receipt['variants'][variant] = {'pages': len(pages), 'changed_pages': len(edits),
                                        'changed_fields': sum(len(x['changes']) for x in edits), 'edits': edits}
    (out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: {a:b for a,b in v.items() if a != 'edits'} for k,v in receipt['variants'].items()}))


if __name__ == '__main__':
    main()
