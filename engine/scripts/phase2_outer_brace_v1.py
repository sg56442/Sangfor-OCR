"""Preserve source-supported outer braces with safe literal serialization."""
import math
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'code/research'))
from outer_brace_0068_v3 import transform as source_transform


def transform(image, block):
    box = block.get('bbox')
    if not isinstance(box, (tuple, list)) or len(box) != 4:
        return None, 'invalid_bbox'
    if not all(isinstance(x, (float, int)) and math.isfinite(x) and 0 <= x <= 1 for x in box):
        return None, 'invalid_bbox'
    if box[0] >= box[2] or box[1] >= box[3]:
        return None, 'invalid_bbox'
    width, height = image.size
    if round(box[2]*width) <= round(box[0]*width) or round(box[3]*height) <= round(box[1]*height):
        return None, 'empty_pixel_bbox'
    content = block.get('content')
    if not isinstance(content, str):
        return None, 'invalid_content'
    # Literal TeX control characters must not become commands inside \text{}.
    literal = re.sub(r'\\\(.*?\\\)', '', content, flags=re.S)
    if any(char in literal for char in '#%&_~^'):
        return None, 'unsafe_literal_tex_character'
    return source_transform(image, block)
