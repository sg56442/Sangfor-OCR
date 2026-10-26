"""Propose canonical TeX groups; accept only identical full-expression renders.

Only redundant grouping syntax is proposed for deletion. Required macro and
script arguments retain their outer braces. Render comparison is a necessary
gate, not a claim that the original recognition was correct.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import fitz
import numpy as np
from pylatexenc.latexwalker import (
    LatexWalker, LatexGroupNode, LatexMacroNode, LatexMathNode,
)

CELL = re.compile(r'(<(?:td|th)\b[^>]*>)(.*?)(</(?:td|th)>)', re.I | re.S)
RECURSIVE_ARGS = {
    'frac', 'dfrac', 'tfrac', 'sqrt', 'mathrm', 'mathbf', 'mathsf', 'mathtt',
    'mathit', 'mathnormal', 'mathbb', 'mathcal', 'mathfrak', 'overline',
    'underline', 'bar', 'hat', 'tilde', 'vec', 'dot', 'ddot', 'widehat',
    'widetilde', 'breve', 'check', 'binom', 'dbinom', 'tbinom',
}
SAFE_MACROS = RECURSIVE_ARGS | set('''
alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa
lambda mu nu xi pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega
Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega
left right big Big bigg Bigg bigl bigr Bigl Bigr biggl biggr Biggl Biggr
text textrm textsf texttt textnormal operatorname mathop mathrel mathbin mathord
mathopen mathclose mathpunct displaystyle textstyle scriptstyle scriptscriptstyle
sum prod coprod int iint iiint oint lim log ln exp sin cos tan cot sec csc
sinh cosh tanh min max sup inf det dim gcd Pr
pm mp times div cdot ast star circ bullet oplus otimes odot
le leq leqslant ge geq geqslant ne neq equiv approx simeq sim cong propto
in notin ni subset supset subseteq supseteq cap cup land lor neg emptyset
forall exists partial nabla infty angle triangle bigtriangleup perp parallel
to rightarrow leftarrow leftrightarrow Rightarrow Leftarrow Leftrightarrow mapsto
uparrow downarrow Uparrow Downarrow longrightarrow longleftarrow
ldots cdots dots vdots ddots prime doubleprime ell hbar imath jmath Re Im
langle rangle lvert rvert lVert rVert vert Vert lbrace rbrace lbrack rbrack
quad qquad thinspace enspace ensuremath
'''.split())


def propose_cell(text):
    try:
        nodes, start, length = LatexWalker(text, tolerant_parsing=False).get_latex_nodes()
        if start != 0 or length != len(text):
            return []
    except Exception:
        return []
    proposals = []
    for math in nodes:
        if not isinstance(math, LatexMathNode) or math.displaytype != 'inline':
            continue
        before = text[math.pos:math.pos+math.len]
        if not before.isascii() or '%' in before or '#' in before:
            continue
        commands = re.findall(r'\\([A-Za-z]+|[^A-Za-z])', before)
        if any(c not in SAFE_MACROS and c not in '{}_ ,;:!|$&' for c in commands):
            continue

        def compose(start, end, replacements):
            value = text[start:end]
            for a, b, replacement in sorted(replacements, reverse=True):
                value = value[:a-start] + replacement + value[b-start:]
            return value

        def items(seq, start, end):
            edits = []
            for i, node in enumerate(seq or []):
                replacement = text[node.pos:node.pos+node.len]
                if isinstance(node, LatexGroupNode) and node.delimiters == ('{', '}'):
                    inner = items(node.nodelist, node.pos+1, node.pos+node.len-1)
                    prefix = text[start:node.pos].rstrip()
                    previous = next((n for n in reversed(seq[:i])
                                     if text[n.pos:n.pos+n.len].strip()), None)
                    required = prefix.endswith(('_', '^', '\\')) or isinstance(previous, LatexMacroNode)
                    replacement = '{'+inner+'}' if required or not inner.strip() else inner
                elif isinstance(node, LatexMacroNode) and node.macroname in RECURSIVE_ARGS:
                    nested = []
                    for arg in getattr(node.nodeargd, 'argnlist', []) or []:
                        if isinstance(arg, LatexGroupNode) and arg.delimiters == ('{', '}'):
                            inner = items(arg.nodelist, arg.pos+1, arg.pos+arg.len-1)
                            nested.append((arg.pos, arg.pos+arg.len, '{'+inner+'}'))
                    replacement = compose(node.pos, node.pos+node.len, nested)
                # Text macros, environments and all unknown argument schemas
                # are opaque. Their arguments cannot be rewritten as math.
                if replacement != text[node.pos:node.pos+node.len]:
                    edits.append((node.pos, node.pos+node.len, replacement))
            return compose(start, end, edits)

        inner_start = math.pos + len(math.delimiters[0])
        inner_end = math.pos + math.len - len(math.delimiters[1])
        after = math.delimiters[0]+items(math.nodelist, inner_start, inner_end)+math.delimiters[1]
        if before != after:
            # No literal glyph, command, font, number or operator is changed.
            assert re.sub(r'(?<!\\)[{}]', '', before) == re.sub(r'(?<!\\)[{}]', '', after)
            proposals.append(dict(start=math.pos, end=math.pos+math.len, before=before, after=after))
    return proposals


def proposals(markup):
    return [(p['before'], p['after']) for c in CELL.finditer(markup) for p in propose_cell(c[2])]


def transform(markup, renderer):
    changes = []
    def cell(match):
        text = match[2]
        edits = []
        for p in propose_cell(text):
            evidence = renderer.check(p['before'], p['after'])
            if evidence['identical']:
                edits.append(p)
        for p in reversed(edits):
            text = text[:p['start']] + p['after'] + text[p['end']:]
        if edits:
            changes.append(dict(before=match[2], after=text, edits=edits))
        return match[1]+text+match[3]
    return CELL.sub(cell, markup), changes


class Renderer:
    """Fresh source-expression memoization within this invocation only."""
    def __init__(self, output, maximum=512):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.maximum = maximum
        self.results = {}

    def check(self, before, after):
        key = (before, after)
        if key in self.results:
            return self.results[key]
        assert len(self.results) < self.maximum, 'Declared render-pair budget exhausted'
        index = len(self.results)
        folder = self.output/f'{index:04d}'
        folder.mkdir()
        docs = [r'\documentclass{article}', r'\usepackage{amsmath,amssymb}',
                r'\usepackage[paperwidth=2000pt,paperheight=600pt,margin=20pt]{geometry}',
                r'\pagestyle{empty}', r'\setlength{\parindent}{0pt}',
                r'\begin{document}']
        for i, expression in enumerate((before, after)):
            if i:
                docs.append(r'\newpage')
            docs.extend([r'\setbox0=\hbox{'+expression+'}',
                         r'\typeout{RSIDIM'+str(i)+r':\the\wd0,\the\ht0,\the\dp0}',
                         r'\vspace*{50pt}\noindent\box0\par'])
        docs.append(r'\end{document}')
        (folder/'compare.tex').write_text('\n'.join(docs)+'\n')
        record = dict(index=index, before=before, after=after, identical=False,
                      reason='render_failed', no_extra_model_calls=True)
        with (folder/'compile.log').open('w') as log:
            try:
                run = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error',
                        '-no-shell-escape', 'compare.tex'], cwd=folder,
                        stdout=log, stderr=subprocess.STDOUT, timeout=12,
                        env=dict(os.environ, openin_any='p', openout_any='p'))
                record['returncode'] = run.returncode
            except subprocess.TimeoutExpired:
                record['reason'] = 'compile_timeout'
                run = None
        if run is not None and run.returncode == 0:
            logtext = (folder/'compile.log').read_text()
            dims = re.findall(r'RSIDIM[01]:([0-9.]+)pt,([0-9.]+)pt,([0-9.]+)pt', logtext)
            record['dimensions_pt'] = dims
            if len(dims) == 2 and all(float(w)<1960 and float(h)+float(d)<500 for w,h,d in dims):
                with fitz.open(folder/'compare.pdf') as doc:
                    if len(doc) == 2:
                        pix = [page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False) for page in doc]
                        arr = [np.frombuffer(p.samples, np.uint8).reshape(p.height,p.width,p.n) for p in pix]
                        record['identical'] = bool(np.array_equal(*arr))
                        record['pixel_difference_count'] = int(np.any(arr[0] != arr[1], axis=2).sum())
                        record['reason'] = 'identical_full_expression_render' if record['identical'] else 'visible_layout_difference'
                        record['pixel_sha256'] = [hashlib.sha256(p.samples).hexdigest() for p in pix]
                    else:
                        record['reason'] = 'unexpected_page_count'
            else:
                record['reason'] = 'unmeasured_or_clipped_dimensions'
        self.results[key] = record
        (folder/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
        return record
