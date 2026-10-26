#!/usr/bin/env python3
"""Reproduce independent E application on the caller's current predictions."""
import argparse
import collections
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code/runtime'))
from e_apply_current_v1 import select_and_apply
from mineru_vl_utils.post_process import json2md


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--e', required=True)
    a = p.parse_args()
    source = Path(a.e).resolve()
    assert source.is_relative_to(ROOT)
    out = source / 'applied/selected'
    shutil.copytree(source / 'baseline/predictions', out)
    props = json.loads((source / 'proposals.json').read_text())
    groups, answers = collections.defaultdict(list), collections.defaultdict(dict)
    for prop in props:
        groups[prop['page']].append(prop)
    for response in json.loads((source / 'recognition.json').read_text()):
        answers[response['proposal']][response['kind']] = response['content']
    records = []
    for pid, proposals in groups.items():
        rawpath = out / 'raw' / (pid + '.json')
        raw = json.loads(rawpath.read_text())
        blocks, recs = select_and_apply(raw['blocks'], proposals, answers)
        if blocks != raw['blocks']:
            raw['blocks'] = blocks
            rawpath.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n')
            (out / 'markdown' / (pid + '.md')).write_text(json2md(blocks))
        records.extend(dict(x, page_diagnostic_only=pid) for x in recs)
    (source / 'applied/receipt.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
