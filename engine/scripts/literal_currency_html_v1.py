#!/usr/bin/env python3
"""Serialize plain paragraphs' escaped currency as an equivalent HTML entity.

Literal dollars stay visible. Mathematical and Markdown-rich paragraphs are
left unchanged; this is format compatibility, not additional recognition.
"""
import html
import re

CURRENCY = re.compile(r'(?<!\\)\\\$(?=\d)')


def encode(content):
    if not isinstance(content, str) or not CURRENCY.search(content):
        return content, []
    # A raw HTML block would disable Markdown interpretation inside it.
    # Therefore only plain, single-line prose can be represented this way.
    if '\n' in content or '\r' in content or re.search(r'[*_`\[\]<>#|]', content):
        return content, []
    plain = CURRENCY.sub('$', content)
    if '\\' in plain or re.search(r'(?<!\\)\$', CURRENCY.sub('', content)):
        return content, []
    encoded = html.escape(plain, quote=False).replace('$', '&#36;')
    result = '<div>' + encoded + '</div>'
    return result, [dict(before=r'\$', after='&#36;', kind='literal_currency_entity')
                    for _ in CURRENCY.finditer(content)]
