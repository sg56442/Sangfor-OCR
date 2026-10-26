"""Input-only line-art/image census; no annotations or diagnostic lists are read."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def features(image):
    # Measurement resize only. Future model views retain the entire original owner.
    thumb = image.copy()
    thumb.thumbnail((1200, 1200))
    gray = np.asarray(thumb.convert('L'))
    height, width = gray.shape
    _, _, stats, _ = cv2.connectedComponentsWithStats((gray < 180).astype('uint8'), 8)
    glyphs = [list(map(int, s)) for s in stats[1:]
              if s[4] >= 8 and 4 <= s[3] <= .2*height and 2 <= s[2] <= .2*width
              and .12 <= s[2]/s[3] <= 6]
    long_lines = [list(map(int, s)) for s in stats[1:]
                  if s[4] >= 12 and (s[2] >= .5*width or s[3] >= .35*height)
                  and s[4]/(s[2]*s[3]) < .3]
    rows = []
    for glyph in sorted(glyphs, key=lambda s: (s[1]+s[3]/2, s[0])):
        cy = glyph[1]+glyph[3]/2
        matches = [r for r in rows if abs(cy-r['cy']) <= .45*min(glyph[3], r['median_height'])]
        if matches:
            row = min(matches, key=lambda r:abs(cy-r['cy']))
            row['glyphs'].append(glyph)
            row['cy'] = float(np.median([g[1]+g[3]/2 for g in row['glyphs']]))
            row['median_height'] = float(np.median([g[3] for g in row['glyphs']]))
        else:
            rows.append(dict(cy=cy, median_height=float(glyph[3]), glyphs=[glyph]))
    bands = []
    for row in rows:
        gs = row['glyphs']
        box = [min(g[0] for g in gs), min(g[1] for g in gs),
               max(g[0]+g[2] for g in gs), max(g[1]+g[3] for g in gs)]
        if len(gs) >= 4 and box[2]-box[0] >= .35*width:
            bands.append(dict(box=box, count=len(gs), median_height=row['median_height']))
    bright = float(np.mean(gray >= 210))
    return dict(measurement_size=[width, height], bright_fraction=bright,
                glyph_count=len(glyphs), line_components=long_lines, bands=bands,
                eligible=bright >= .65 and bool(long_lines) and bool(bands))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    source, out = Path(args.inputs).resolve(), Path(args.out).resolve()
    root = Path(__file__).resolve().parents[1]
    assert out.is_relative_to(root) and not out.exists()
    out.mkdir(parents=True)
    pages = json.loads(Path(args.manifest).read_text())
    start = time.monotonic()
    records, bindings = [], []
    for page in pages:
        raw_path = source/'raw'/(page['id']+'.json')
        raw = json.loads(raw_path.read_text())
        bindings.append(dict(raw=str(raw_path), sha256=sha(raw_path)))
        parents = [(i,b) for i,b in enumerate(raw['blocks'])
                   if b['type'] == 'image' and b.get('angle') in [None, 0] and not b.get('content')]
        if not parents:
            continue
        with Image.open(page['image']) as original:
            image = original.convert('RGB')
            for index, parent in parents:
                box = [round(v*(image.width if i%2 == 0 else image.height))
                       for i,v in enumerate(parent['bbox'])]
                if box[2]-box[0] < 84 or box[3]-box[1] < 84:
                    continue
                crop = image.crop(box)
                f = features(crop)
                records.append(dict(ordinal=len(records), page=page['id'], owner=index,
                    source=page['image'], source_sha256=sha(page['image']), raw=str(raw_path),
                    raw_sha256=sha(raw_path), rect=box, bbox=parent['bbox'], features=f))
    receipt = dict(pages=len(pages), input_bindings=bindings, records=records,
                   eligible=sum(r['features']['eligible'] for r in records),
                   eligible_pages=len({r['page'] for r in records if r['features']['eligible']}),
                   HTTP=0, source_hashes={str(Path(__file__).resolve()):sha(__file__)},
                   manifest_sha256=sha(args.manifest), wall_seconds=time.monotonic()-start,
                   limitation='Glyph-like components and line-art only; not a math detector or verified omissions.')
    (out/'census.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print({k:v for k,v in receipt.items() if k not in ['input_bindings','records','source_hashes']})


if __name__ == '__main__':
    main()
