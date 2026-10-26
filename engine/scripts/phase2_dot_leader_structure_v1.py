"""Pure image/current-table dot-leader index structure; no learned observations.

The generated candidate keeps every existing character and row in order. This
module only proposes an unadopted alternative; source reviews and scoring are
separate. Page names, GT and source labels are not function inputs.
"""
import re

import cv2
import numpy as np
from lxml import html


def intervals(mask):
    changes = np.diff(np.r_[False, mask, False].astype(np.int8))
    return list(zip(np.where(changes == 1)[0], np.where(changes == -1)[0]))


def transform(image, markup):
    evidence = dict(selected=False, reason='not_plain_single_column')
    try:
        root = html.fromstring(markup)
    except (ValueError, TypeError):
        return markup, evidence
    if root.tag != 'table' or len(root.xpath('.//table')):
        return markup, evidence
    rows = root.xpath('./tr|./tbody/tr')
    cells = []
    for row in rows:
        children = list(row)
        if (len(children) != 1 or children[0].tag != 'td' or children[0].attrib
                or len(children[0])):
            return markup, evidence
        cells.append(children[0].text or '')
    raw_cells = re.findall(r'<td>(.*?)</td>', markup, re.S)
    if len(raw_cells) != len(cells) or len(cells) < 4:
        return markup, evidence
    # A narrow structural index syntax: a literal leader followed by page-like
    # tokens, with no word dictionary or known answer strings.
    pattern = re.compile(r'(.+?\.{3,})([A-Za-z]*\d+(?:\s*[,\-–]\s*[A-Za-z]*\d+)*)')
    parsed = [pattern.fullmatch(text) for text in raw_cells]
    count = sum(m is not None for m in parsed)
    if count < 3 or any(not m and not re.fullmatch(r'[A-Za-z](?:[-–][A-Za-z])?', t.strip())
                        for t, m in zip(cells, parsed)):
        evidence['reason'] = 'no_repeated_index_schema'
        return markup, evidence
    gray = np.asarray(image.convert('L'))
    height, width = gray.shape
    ink = (gray < 160).astype(np.uint8)
    _, _, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    glyphs = stats[1:]
    supported = glyphs[(glyphs[:, 3] >= 4) & (glyphs[:, 4] >= 5)
                       & (glyphs[:, 2] <= 3 * glyphs[:, 3])
                       & (glyphs[:, 3] < .1 * height)]
    if len(supported) < 12:
        evidence['reason'] = 'insufficient_glyph_support'
        return markup, evidence
    glyph_height = float(np.percentile(supported[:, 3], 75))
    unit = max(1., .25 * glyph_height)
    dots = sorted([list(map(int, s)) for s in glyphs
                   if 1 <= s[2] <= unit and 1 <= s[3] <= unit
                   and s[4] <= unit * unit], key=lambda s: (s[1], s[0]))
    bands = []
    for dot in dots:
        if bands and abs(dot[1] - np.median([d[1] for d in bands[-1]])) <= max(1., .08 * glyph_height):
            bands[-1].append(dot)
        else:
            bands.append([dot])
    leaders = []
    for band in bands:
        groups, current = [], []
        for dot in sorted(band):
            if current and dot[0] - current[-1][0] > unit * 2:
                groups.append(current)
                current = []
            current.append(dot)
        groups.append(current)
        for group in groups:
            if len(group) < 4:
                continue
            gaps = np.diff([d[0] for d in group])
            pitch = float(np.median(gaps))
            if pitch <= 0 or max(abs(gaps - pitch)) > max(1., .35 * pitch):
                continue
            y = float(np.median([d[1] for d in group]))
            end = group[-1][0] + group[-1][2]
            # A separated glyph cluster must occupy the suffix lane. Its exact
            # transcription comes only from the current native output.
            terminal = [s for s in glyphs if s[0] >= end and s[3] > unit
                        and s[1] <= y + .15 * glyph_height
                        and s[1] + s[3] >= y - .25 * glyph_height]
            if not terminal:
                continue
            left = min(int(s[0]) for s in terminal)
            right = max(int(s[0] + s[2]) for s in terminal)
            if left - end > glyph_height or right < .85 * width:
                continue
            leaders.append(dict(y=y, x0=group[0][0], x1=end, terminal_left=left,
                                terminal_right=right, dots=len(group)))
    leaders.sort(key=lambda d: d['y'])
    evidence.update(glyph_height=glyph_height, native_index_rows=count, source_leaders=leaders)
    if len(leaders) != count:
        evidence['reason'] = 'source_and_native_leader_count_differ'
        return markup, evidence
    if max(x['terminal_right'] for x in leaders) - min(x['terminal_right'] for x in leaders) > .35 * glyph_height:
        evidence['reason'] = 'terminal_right_axis_not_consistent'
        return markup, evidence
    # Full-width pale bands carry group headers, rather than individual data
    # cells. This also gives a source-based check of the complete row sequence.
    header_bands = [(int(a), int(b)) for a, b in intervals(((gray > 170) & (gray < 235)).mean(1) > .75)
                    if b - a >= .35 * glyph_height]
    events = sorted([(d['y'], 'record') for d in leaders]
                    + [((a+b)/2, 'header') for a, b in header_bands])
    expected = ['record' if m else 'header' for m in parsed]
    evidence['header_bands'] = header_bands
    if [kind for _, kind in events] != expected:
        evidence['reason'] = 'source_row_sequence_differs'
        return markup, evidence
    choices = iter(parsed)
    def replace(match):
        split = next(choices)
        if split:
            return '<td>' + split[1] + '</td><td>' + split[2] + '</td>'
        return '<td colspan="2">' + match[1] + '</td>'
    candidate = re.sub(r'<td>(.*?)</td>', replace, markup, flags=re.S)
    after = html.fromstring(candidate)
    assert ''.join(root.itertext()) == ''.join(after.itertext())
    assert len(after.xpath('./tr|./tbody/tr')) == len(rows)
    evidence.update(selected=True, reason='index_schema_source_leaders_headers_and_terminal_axis',
                    existing_character_stream_preserved=True)
    return candidate, evidence
