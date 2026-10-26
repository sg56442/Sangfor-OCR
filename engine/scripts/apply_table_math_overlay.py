#!/usr/bin/env python3
"""Apply syntax-safe equivalent table math serialization after block composition."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from mineru_vl_utils.post_process import json2md
import probe_table_math_canonical as canonical

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--combined', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    source, out = Path(a.combined).resolve(), Path(a.out).resolve()
    assert out.is_relative_to(ROOT)
    canonical.checks()
    frozen_hash = sha(canonical.__file__)
    out.mkdir(parents=True, exist_ok=False)
    for folder in ['predictions/raw', 'predictions/markdown', 'provenance']:
        (out / folder).mkdir(parents=True)
    counts = dict(pages=0, changed_pages=0, changed_table_blocks=0, changed_fields=0)
    edits = []
    for mdpath in sorted((source / 'predictions/markdown').glob('*.md')):
        rawpath = source / 'predictions/raw' / (mdpath.stem + '.json')
        raw = json.loads(rawpath.read_text())
        records = []
        for i, block in enumerate(raw['blocks']):
            if block['type'] != 'table':
                continue
            result, changes = canonical.transform(block['content'], 'canonical')
            if changes:
                block['content'] = result
                records.append({'block_index': i, 'changes': changes})
        expected_md, changes = canonical.transform(mdpath.read_text(), 'canonical')
        destination_md, destination_raw = out / 'predictions/markdown' / mdpath.name, out / 'predictions/raw' / rawpath.name
        if records:
            assert json2md(raw['blocks']) == expected_md, 'Raw/Markdown transformation disagreement: ' + mdpath.stem
            destination_raw.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n')
            destination_md.write_text(expected_md)
            edits.append({'page_locator': mdpath.stem, 'records': records})
        else:
            assert not changes
            shutil.copyfile(rawpath, destination_raw)
            shutil.copyfile(mdpath, destination_md)
        provenance = json.loads((source / 'provenance' / rawpath.name).read_text())
        provenance.update(table_math_canonical=records, prior_candidate_raw_sha256=sha(rawpath),
                          candidate_raw_sha256=sha(destination_raw), candidate_markdown_sha256=sha(destination_md))
        (out / 'provenance' / rawpath.name).write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n')
        counts['pages'] += 1
        counts['changed_pages'] += bool(records)
        counts['changed_table_blocks'] += len(records)
        counts['changed_fields'] += len(changes)
    assert frozen_hash == sha(canonical.__file__)
    parent = json.loads((source / 'composition_receipt.json').read_text())
    receipt = dict(status='COMPLETE', prior=str(source), counts=counts,
                   order=parent['order'] + ['TABLE_MATH_CANONICAL'], changes=edits,
                   code_sha256=frozen_hash, model_calls=0, runtime_GT=False,
                   raw_markdown_parity='PASS', semantic_boundary_checks='PASS',
                   scope='Equivalent representation; no improved recognition claim')
    (out / 'composition_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
