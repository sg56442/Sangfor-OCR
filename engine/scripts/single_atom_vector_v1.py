"""Portable representation of a single Latin vector atom; no data or file inputs."""
import re
from pylatexenc.latexwalker import LatexWalker, LatexMacroNode

def convert(content):
    if '\\overrightarrow' not in content:
        return content, []
    try:
        nodes, start, length = LatexWalker(content, tolerant_parsing=False).get_latex_nodes()
        assert start == 0 and length == len(content)
    except Exception:
        return content, []
    edits = []
    def walk(items):
        for node in items or []:
            if isinstance(node, LatexMacroNode):
                if node.macroname in {'text', 'textrm', 'textbf', 'verb', 'url', 'operatorname'}:
                    continue
                args = getattr(node.nodeargd, 'argnlist', []) or []
                if node.macroname == 'overrightarrow' and len(args) == 1 and args[0] is not None:
                    arg = args[0]
                    value = content[arg.pos+1:arg.pos+arg.len-1].strip()
                    if getattr(arg, 'delimiters', None) == ('{', '}') and re.fullmatch('[A-Za-z]', value):
                        edits.append(dict(start=node.pos, end=node.pos+node.len,
                                          before=content[node.pos:node.pos+node.len], after='\\vec{' + value + '}'))
                        continue
                for arg in args:
                    walk(getattr(arg, 'nodelist', None))
            else:
                walk(getattr(node, 'nodelist', None))
    walk(nodes)
    for edit in sorted(edits, key=lambda x:x['start'], reverse=True):
        content = content[:edit['start']] + edit['after'] + content[edit['end']:]
    return content, edits
