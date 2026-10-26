"""Remove redundant outer groups around single-glyph math atoms in table cells.

The command, its argument, all characters and scripts remain unchanged. This
is a serialization candidate, not character recovery. No file/model inputs.
"""
import re

from pylatexenc.latexwalker import (
    LatexWalker, LatexGroupNode, LatexMacroNode, LatexMathNode,
)

CELL = re.compile(r'(<(?:td|th)\b[^>]*>)(.*?)(</(?:td|th)>)', re.I | re.S)
ATOMS = {
    'mathrm', 'mathbf', 'mathsf', 'mathit', 'mathtt', 'mathnormal',
    'mathbb', 'mathcal', 'mathfrak', 'widetilde', 'overline', 'vec',
    'bar', 'hat', 'tilde', 'dot', 'ddot', 'widehat', 'breve', 'check',
}


def atom_inner(text, group):
    if not isinstance(group, LatexGroupNode) or group.delimiters != ('{', '}'):
        return None
    children = [n for n in group.nodelist if text[n.pos:n.pos+n.len].strip()]
    if len(children) != 1 or not isinstance(children[0], LatexMacroNode):
        return None
    macro = children[0]
    args = getattr(macro.nodeargd, 'argnlist', []) or []
    if macro.macroname not in ATOMS or len(args) != 1:
        return None
    arg = args[0]
    if not isinstance(arg, LatexGroupNode) or arg.delimiters != ('{', '}'):
        return None
    if not re.fullmatch('[A-Za-z0-9]', text[arg.pos+1:arg.pos+arg.len-1]):
        return None
    return text[group.pos+1:group.pos+group.len-1]


def simplify_cell(text):
    try:
        nodes, start, length = LatexWalker(text, tolerant_parsing=False).get_latex_nodes()
        if start != 0 or length != len(text):
            return text, []
    except Exception:
        return text, []
    edits = []
    for math in nodes:
        if not isinstance(math, LatexMathNode):
            continue
        # Only direct formula children, never macro arguments, text, script
        # bodies, environments or unsupported nested command structures.
        for index, node in enumerate(math.nodelist):
            replacement = atom_inner(text, node)
            if replacement is None:
                continue
            prefix = text[math.pos:node.pos].rstrip()
            if prefix.endswith(('_', '^', '\\')):
                continue
            previous = next((n for n in reversed(math.nodelist[:index])
                             if text[n.pos:n.pos+n.len].strip()), None)
            if isinstance(previous, LatexMacroNode):
                continue
            edits.append(dict(start=node.pos, end=node.pos+node.len,
                              before=text[node.pos:node.pos+node.len], after=replacement,
                              formula=text[math.pos:math.pos+math.len]))
    for e in reversed(edits):
        text = text[:e['start']] + e['after'] + text[e['end']:]
    return text, edits


def transform(markup):
    changes = []
    def cell(match):
        after, edits = simplify_cell(match[2])
        if edits:
            changes.append(dict(before=match[2], after=after, edits=edits))
        return match[1] + after + match[3]
    return CELL.sub(cell, markup), changes
