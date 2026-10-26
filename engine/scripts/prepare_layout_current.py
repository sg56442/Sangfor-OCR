#!/usr/bin/env python3
"""Build frozen local layout/rowpair requests from caller current native inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code/runtime'))
from layout_current_v1 import bind
from layout_frozen_proposals_v1 import proposals


def load(p):
    return json.loads(Path(p).read_text())


def save(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def prepare(native, pages, e, out):
    native, out = Path(native), Path(out).resolve()
    assert out.is_relative_to(ROOT)
    images = {p['id']: p['image'] for p in pages}
    groups = []
    for page in pages:
        blocks = load(native / 'raw' / (page['id'] + '.json'))['blocks']
        groups.extend(dict(p, page=page['id'], stratum='frozen') for p in proposals(blocks))
    dense = [dict(page=p['page'], indices=[p['index']], bbox=p['bbox'], stratum='all_current_E')
             for p in load(Path(e) / 'proposals.json')]
    receipts = {}
    for family, props in [('group', groups), ('dense', dense)]:
        folder = out / family
        folder.mkdir(parents=True, exist_ok=False)
        for kind in ['raw', 'markdown']:
            (folder / 'baseline/predictions' / kind).mkdir(parents=True)
        bound, requests, tiles = [], [], []
        for i, prop in enumerate(props):
            p = dict(prop, proposal_id=i, normal_control=False)
            image = Image.open(images[p['page']]).convert('RGB')
            width, height = image.size
            rect = [round(v*f) for v, f in zip(p['bbox'], [width, height, width, height])]
            crop = image.crop(rect)
            path = folder / ('p' + str(i) + '.png')
            crop.save(path)
            rawpath = native / 'raw' / (p['page'] + '.json')
            p.update(pixel_rect=rect, page_size=[width, height], crop_size=list(crop.size),
                     source_image=images[p['page']], source_native_sha256=hashlib.sha256(rawpath.read_bytes()).hexdigest())
            bound.append(bind(load(rawpath)['blocks'], image, p))
            tiles.append(dict(id='p' + str(i), image=str(path)))
            requests.append(dict(proposal=i, image=str(path), kind='layout', task='[layout]', bbox=p['bbox'],
                                 size=list(crop.size), affine_candidate_to_page=[1, 0, rect[0], 0, 1, rect[1]],
                                 encoded_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        for pid in {p['page'] for p in props}:
            for kind, suffix in [('raw', '.json'), ('markdown', '.md')]:
                shutil.copyfile(native / kind / (pid + suffix), folder / 'baseline/predictions' / kind / (pid + suffix))
        for name, value in [('proposals', bound), ('requests', requests), ('tiles', tiles)]:
            save(folder / (name + '.json'), value)
        receipts[family] = dict(configured=len(props), runtime_GT=False, diagnostic_controls_added=False,
                               caller_native=str(native.resolve()), input_pages=len(pages))
        save(folder / 'preparation.json', receipts[family])
    save(out / 'preparation.json', receipts)
    return receipts


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ['native', 'pages', 'e', 'out']:
        p.add_argument('--' + key, required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.native, load(a.pages), a.e, a.out)))
