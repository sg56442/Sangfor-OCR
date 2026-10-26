#!/usr/bin/env python3
"""Serialize complete numeric arithmetic equalities in table cells as math.

No arithmetic is evaluated or corrected. Identifiers, units, currency, mixed
text/math and index labels without an arithmetic operation are unchanged.
"""
import re

CELL = re.compile(r'(<(?:td|th)\b[^>]*>)(.*?)(</(?:td|th)>)', re.S | re.I)
TOKEN = re.compile(r'\d+(?:\.\d+)?|[()+\-−×÷*/=]')


def expression(value):
    # Exclude punctuation/unknown characters before tokenization; whitespace
    # may separate tokens but may not concatenate separate numeric atoms.
    if not re.fullmatch(r'[\d\s.()+\-−×÷*/=]+', value) or value.count('=') != 1:
        return None
    tokens = TOKEN.findall(value)
    if ''.join(tokens) != re.sub(r'\s', '', value):
        return None
    index, binary = 0, 0

    def atom():
        nonlocal index
        if index < len(tokens) and tokens[index] in ['+', '-', '−']:
            index += 1
        if index >= len(tokens):
            raise ValueError('missing atom')
        if tokens[index] == '(':
            index += 1
            arithmetic()
            if index >= len(tokens) or tokens[index] != ')':
                raise ValueError('unclosed parentheses')
            index += 1
        elif re.fullmatch(r'\d+(?:\.\d+)?', tokens[index]):
            index += 1
        else:
            raise ValueError('non numeric atom')

    def arithmetic():
        nonlocal index, binary
        atom()
        while index < len(tokens) and tokens[index] in ['+', '-', '−', '×', '÷', '*', '/']:
            binary += 1
            index += 1
            atom()

    try:
        arithmetic()
        if index >= len(tokens) or tokens[index] != '=':
            return None
        index += 1
        arithmetic()
        if index != len(tokens) or not binary:
            return None
    except ValueError:
        return None
    mapping = {'−': '-', '×': r'\times ', '÷': r'\div ', '*': r'\ast '}
    return ''.join(mapping.get(token, token) for token in tokens)


def transform(markup):
    edits = []

    def cell(match):
        body = expression(match[2])
        if body is None:
            return match[0]
        after = '$' + body + '$'
        edits.append(dict(before=match[2], after=after,
                          attribution='numeric arithmetic math serialization; no content correction'))
        return match[1] + after + match[3]

    return CELL.sub(cell, markup), edits
