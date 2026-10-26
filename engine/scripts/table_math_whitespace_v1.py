#!/usr/bin/env python3
"""Remove TeX-ignored math whitespace, retaining command and text boundaries."""
import re

from pylatexenc.latexwalker import LatexWalker,LatexMacroNode,get_default_latex_context_db

CELL=re.compile(r'(<(?:td|th)\b[^>]*>)(.*?)(</(?:td|th)>)',re.S|re.I)
INLINE=re.compile(r'(?<!\\)\\\((.*?)\\\)',re.S)
CONTEXT=get_default_latex_context_db()
TEXT_MACROS={'text','textrm','textsf','texttt','textnormal','textbf','textit','mathrm','mathbf',
             'mathit','mathsf','mathtt','mathnormal','operatorname','mbox','hbox','vbox',
             'url','href','label','ref','tag','verb','color','textcolor'}
SYMBOLS=set('alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu xi omicron pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega pm mp times div cdot ast star circ bullet le leq leqslant ge geq geqslant neq approx sim simeq equiv propto in notin ni subset supset subseteq supseteq emptyset varnothing infinity infty partial nabla sum prod int oint lim log ln sin cos tan exp min max sup inf det deg gcd left right quad qquad hfill uparrow downarrow leftarrow rightarrow leftrightarrow to mapsto implies dots cdots ldots vdots ddots forall exists neg land lor cup cap perp parallel angle triangle square checked checkmark surd'.split())


def compact(expression):
    if '%' in expression:return expression,'percent_or_comment_declined'
    try:
        nodes,start,length=LatexWalker(expression,tolerant_parsing=False).get_latex_nodes()
        if start!=0 or length!=len(expression):return expression,'incomplete_parse'
    except Exception:return expression,'parse_failure'
    protected=[];unknown=[]
    def visit(items):
        for node in items or []:
            if isinstance(node,LatexMacroNode):
                name=node.macroname
                if name in TEXT_MACROS:
                    protected.append((node.pos,node.pos+node.len));continue
                if len(name)>1 and CONTEXT.get_macro_spec(name) is None and name not in SYMBOLS:unknown.append(name)
                for arg in (getattr(node.nodeargd,'argnlist',[]) or []):visit(getattr(arg,'nodelist',None))
            else:visit(getattr(node,'nodelist',None))
    visit(nodes)
    if unknown:return expression,'unknown_macro_declined'
    def replace(m):
        if any(a<=m.start()<b for a,b in protected):return m.group(0)
        prefix=expression[:m.start()];suffix=expression[m.end():]
        slashes=len(prefix)-len(prefix.rstrip('\\'))
        if slashes%2:return m.group(0) # explicit TeX control-space
        if re.search(r'(?<!\\)\\[A-Za-z]+$',prefix) and suffix[:1].isalpha():return ' '
        return ''
    return re.sub(r'\s+',replace,expression),'math_whitespace_only'


def transform(markup):
    changes=[]
    def cell(m):
        def formula(q):
            after,reason=compact(q.group(1))
            if after==q.group(1):return q.group(0)
            changes.append(dict(before=q.group(1),after=after,reason=reason))
            return r'\('+after+r'\)'
        return m.group(1)+INLINE.sub(formula,m.group(2))+m.group(3)
    return CELL.sub(cell,markup),changes
