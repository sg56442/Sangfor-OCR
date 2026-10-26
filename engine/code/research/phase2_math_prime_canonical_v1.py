"""Conservative math-only prime spelling: ASCII base^{prime...} -> base'...

Not an equivalence checker or a general TeX parser. Unknown commands reject the
entire math span. No GT, model, page identity, grouping or expression deletion.
"""
import re

TOKEN = re.compile(r'\\[A-Za-z]+|\\[^A-Za-z]|[^\s]')
DELIM = re.compile(r'\\\(|\\\[|\$\$|\$|\\\)|\\\]')
ZERO = {r'\prime', r'\quad', r'\qquad', r'\leq', r'\geq', r'\le', r'\ge',
        r'\neq', r'\ne', r'\times', r'\cdot', r'\pm', r'\mp', r'\infty',
        r'\sum', r'\prod', r'\int', r'\in', r'\notin', r'\subset',
        r'\alpha', r'\beta', r'\gamma', r'\delta', r'\epsilon', r'\theta',
        r'\lambda', r'\mu', r'\pi', r'\sigma', r'\phi', r'\omega',
        r'\ldots', r'\cdots', r'\dots', r'\!', r'\,', r'\;', r'\:'}


def body_transform(body):
    tokens = list(TOKEN.finditer(body)); ts = [m[0] for m in tokens]
    if any(t in ('%', '#', '&', '$', '~', '`') for t in ts):
        return body, [], 'unsupported_character'
    if any(t.startswith('\\') and t not in ZERO | {r'\frac'} for t in ts):
        return body, [], 'unknown_command'
    stack = []; ends = {}
    for i, t in enumerate(ts):
        if t == '{': stack.append(i)
        if t == '}':
            if not stack: return body, [], 'unbalanced_braces'
            ends[stack.pop()] = i
    if stack: return body, [], 'unbalanced_braces'
    for i,t in enumerate(ts):
        if t == r'\frac':
            a=ends.get(i+1)
            if a is None or a+1 not in ends: return body, [], 'macro_arity'
    changes=[]
    for i,t in enumerate(ts):
        if not (len(t)==1 and t.isascii() and t.isalpha()): continue
        if i and ts[i-1] in ('_', '^'): continue
        if ts[i+1:i+3] != ['^', '{']: continue
        end=ends.get(i+2)
        if end is None: continue
        prime=ts[i+3:end]
        if not prime or any(x != r'\prime' for x in prime): continue
        if end+1 < len(ts) and ts[end+1] in ('^','_',"'",r'\prime'):
            return body, [], 'ambiguous_following_script'
        start=tokens[i].start();stop=tokens[end].end()
        changes.append({'start':start,'stop':stop,'before':body[start:stop],
                        'after':t+"'"*len(prime),'base':t,'order':len(prime)})
    out=body
    for c in reversed(changes):out=out[:c['start']]+c['after']+out[c['stop']:]
    return out,changes,'accepted' if changes else 'no_supported_prime'


def transform(text):
    if not isinstance(text, str): return text, []
    # Reject malformed/mixed delimiters globally, rather than pairing across text.
    delimiters=list(DELIM.finditer(text)); spans=[];i=0
    while i<len(delimiters):
        a=delimiters[i];close={r'\(':r'\)',r'\[':r'\]','$':'$','$$':'$$'}.get(a[0])
        if close is None or i+1>=len(delimiters):return text,[]
        b=delimiters[i+1]
        if b[0]!=close:return text,[]
        if (a.start() and text[a.start()-1]=='\\') or (b.start() and text[b.start()-1]=='\\'):
            return text,[]
        spans.append((a.end(),b.start()));i+=2
    changes=[];out=text
    for start,stop in reversed(spans):
        value,records,reason=body_transform(text[start:stop])
        if records:
            out=out[:start]+value+out[stop:]
            changes.append({'span':[start,stop],'before':text[start:stop], 'after':value,'changes':records})
    return out,list(reversed(changes))
