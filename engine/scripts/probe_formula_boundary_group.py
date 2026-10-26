#!/usr/bin/env python3
"""Remove only unmatched, nonprinting group closers at a display's end.

Escaped visible braces, command arguments, scripts and interior errors remain
unchanged. No symbol recognition or page-specific information is involved.
"""
import argparse
import hashlib
import json
from pathlib import Path

from mineru_vl_utils.post_process import json2md

ROOT = Path(__file__).resolve().parents[1]
SLASH = chr(92)


def repair(content):
    stripped = content.strip()
    if not (stripped.startswith(SLASH + '[') and stripped.endswith(SLASH + ']')):
        return content, []
    start = content.index(SLASH + '[') + 2
    end = content.rindex(SLASH + ']')
    inner = content[start:end]
    # Comments/verbatim may change tokenization, so this simple lexer declines.
    if '%' in inner or SLASH + 'verb' in inner:
        return content, []
    stack, orphan = [], []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == SLASH:
            i += 1
            if i < len(inner) and inner[i].isalpha():
                while i < len(inner) and inner[i].isalpha():
                    i += 1
            else:
                i += 1
            continue
        if ch == '{':
            stack.append(i)
        elif ch == '}':
            if stack:
                stack.pop()
            else:
                orphan.append(i)
        i += 1
    if stack or not orphan:
        return content, []
    # Every unmatched close must be part of an otherwise empty trailing suffix.
    if inner[orphan[0]:].replace('}', '').strip():
        return content, []
    chars = list(inner)
    for pos in orphan:
        chars[pos] = ''
    return content[:start] + ''.join(chars) + content[end:], [dict(offset=start + p, removed='}',
        reason='unmatched_nonprinting_trailing_group_closer') for p in orphan]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--combined', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    source, out = Path(a.combined).resolve(), Path(a.out).resolve()
    assert out.is_relative_to(ROOT)
    out.mkdir(parents=True, exist_ok=False)
    for d in ['baseline', 'candidate', 'crops']:
        (out / d).mkdir()
    # Escaped visible braces and internal/superscript scopes must be preserved.
    for s in [r'\[\left\{a\right\}\]', r'\[{a+b}^{2}\]', r'\[a+b}^{2}\]',
              r'\[\begin{array}{cc}a&b\\c&d\end{array}\]', r'\[\text{a}\]']:
        assert repair(s)[0] == s
    assert repair(r'\[a+b}\]')[0] == r'\[a+b\]'
    records, scanned = [], 0
    for rawpath in sorted((source / 'predictions/raw').glob('*.json')):
        raw = json.loads(rawpath.read_text())
        edits = []
        for index, block in enumerate(raw['blocks']):
            if block['type'] != 'equation':
                continue
            scanned += 1
            before = block['content']
            after, changes = repair(before)
            assert repair(after)[0] == after
            if changes:
                block['content'] = after
                edits.append(dict(block_index=index, bbox=block['bbox'], before=before, after=after,
                                  changes=changes))
        if edits:
            md = source / 'predictions/markdown' / (rawpath.stem + '.md')
            (out / 'baseline' / md.name).write_bytes(md.read_bytes())
            (out / 'candidate' / md.name).write_text(json2md(raw['blocks']))
            records.append(dict(page_locator=rawpath.stem, native_raw_sha256=hashlib.sha256(rawpath.read_bytes()).hexdigest(), edits=edits))
    receipt = dict(scanned_formulas=scanned, changed_pages=len(records),
                   changed_blocks=sum(len(r['edits']) for r in records), records=records,
                   runtime_GT=False, new_model_calls=0, source=str(source),
                   source_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out / 'preparation.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['records']}))


if __name__ == '__main__':
    main()
