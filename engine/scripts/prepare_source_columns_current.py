#!/usr/bin/env python3
"""Build source-column requests solely from the caller's current images/blocks."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code/research'))
from source_column_runtime_v4 import propose_source_columns


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ['native', 'pages', 'out']:
        p.add_argument('--' + key, required=True)
    a = p.parse_args()
    native, pages, out = [Path(getattr(a, k)).resolve() for k in ['native', 'pages', 'out']]
    assert out.is_relative_to(ROOT)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'crops').mkdir()
    records, requests = [], []
    for page in json.loads(pages.read_text()):
        path = native / 'raw' / (page['id'] + '.json')
        raw = json.loads(path.read_text())
        with Image.open(page['image']) as image:
            proposals = propose_source_columns(image, raw)
        groups = []
        for prop in proposals:
            inputs = []
            for x in prop['inputs']:
                rid = f'column{len(requests):06d}'
                crop = out / 'crops' / (rid + '.png')
                x['image'].save(crop)
                requests.append(dict(request_id=rid, image_path=str(crop),
                                     pixel_sha256=x['pixel_sha256'], image_size=list(x['image'].size),
                                     source_to_candidate_affine=x['affine']))
                inputs.append(dict(key=x['key'], request_id=rid, pixel_sha256=x['pixel_sha256'],
                                   size=list(x['image'].size), affine=x['affine']))
            groups.append(dict(block_index=prop['block_index'], source_bbox=prop['source_bbox'], inputs=inputs))
        records.append(dict(page_id=page['id'], native_raw_sha256=sha(path),
                            image_sha256=sha(page['image']), proposals=groups))
    save(out / 'requests.json', requests)
    save(out / 'records.json', records)
    receipt = dict(schema='caller_current_source_columns_v1', native=str(native),
                   pages_manifest=str(pages), manifest_sha256=sha(pages), pages=len(records),
                   proposals=sum(len(r['proposals']) for r in records), requests=len(requests),
                   historical_answers=False, runtime_GT=False)
    save(out / 'build_receipt.json', receipt)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
