"""Separate a spaced natural-language formula label, retaining every math token."""
import copy
import re
import cv2
import numpy as np

PREFIX = re.compile(r'^\\\[(\s*)\\text\s*\{([A-Za-z]+(?:[ -][A-Za-z]+)+)\}(\s*\\(?:quad|qquad)\b\s*)([\s\S]*)\\\]$')
OPERAND = re.compile(r'^(?:[=+*/<>_^:;,)-]|\\(?:times|div|cdot|leq?|geq?|approx|equiv|in|notin|to)\b)')


def split(image, block):
    trace = dict(applied=False, reason='not_spaced_natural_label')
    if block.get('type') != 'equation' or block.get('angle', 0) != 0:
        return [block], trace
    text = block.get('content', '')
    match = PREFIX.fullmatch(text)
    if not match or OPERAND.match(match[4].lstrip()) or not match[4].strip():
        return [block], trace
    # Only the leading text wrapper and layout spacing move. The full math remainder
    # (including structured arrays, constraints and internal prose) is byte-preserved.
    label, body = match[2], match[4]
    width, height = image.size
    box = [round(v*(width if i%2 == 0 else height)) for i, v in enumerate(block['bbox'])]
    if not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
        return [block], dict(trace, reason='invalid_owner')
    ink = np.asarray(image.convert('L').crop(box)) < 180
    _, _, stats, _ = cv2.connectedComponentsWithStats(ink.astype('uint8'), 8)
    glyphs = stats[1:]
    glyphs = glyphs[(glyphs[:, 3] >= 5) & (glyphs[:, 4] >= 4)]
    if len(glyphs) < 8:
        return [block], dict(trace, reason='insufficient_source_glyphs')
    scale = float(np.median(glyphs[:, 3]))
    blank = ~ink.any(axis=0)
    gaps, start = [], None
    for i, value in enumerate([*blank, False]):
        if value and start is None:
            start = i
        elif not value and start is not None:
            if start > 0 and i < ink.shape[1] and i-start >= 1.5*scale:
                gaps.append([start, i])
            start = None
    if not gaps:
        return [block], dict(trace, reason='no_source_gap_between_label_and_math')
    first = gaps[0]
    split_x = box[0] + (first[0]+first[1])/2
    left, right = copy.deepcopy(block), copy.deepcopy(block)
    left.update(type='text', content=label)
    right['content'] = '\\['+body+'\\]'
    left['bbox'][2], right['bbox'][0] = split_x/width, split_x/width
    trace.update(applied=True, reason='explicit_natural_label_then_source_gap',
        label=label, original_prefix=text[:match.start(4)], original_body=body,
        math_remainder_byte_preserved=right['content'][2:-2] == body,
        source_box=box, source_glyph_median_height=scale, first_gap=first,
        split_x=split_x, source_threshold=180, gap_over_glyph_height_minimum=1.5)
    return [left, right], trace
