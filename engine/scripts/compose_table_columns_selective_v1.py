#!/usr/bin/env python3
"""Apply source-column decisions with current-origin and consumed-input checks."""
import argparse
import collections
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

from PIL import Image
from mineru_vl_utils.post_process import json2md

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code/research'))
import source_column_request_gate_v1 as columns_api
import native_column_consolidation_api as consolidation_api


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ['native', 'pages', 'combined', 'columns', 'answers', 'out']:
        p.add_argument('--' + key, required=True)
    p.add_argument('--consolidation', action='store_true')
    a = p.parse_args()
    native, pages, prior, columns, answers_dir, out = [Path(getattr(a, k)).resolve()
        for k in ['native', 'pages', 'combined', 'columns', 'answers', 'out']]
    assert out.is_relative_to(ROOT)
    build = load(columns / 'build_receipt.json')
    assert build['schema'] == 'caller_current_source_columns_v1'
    assert Path(build['native']).resolve() == native
    assert build['manifest_sha256'] == sha(pages)
    receipt = load(answers_dir / 'receipt.json')
    assert receipt['status'] == 'COMPLETE'
    assert receipt['request_manifest_sha256'] == sha(columns / 'requests.json')
    assert receipt['model'] == load(ROOT / 'agents/shared/runtime.json')['model']
    answers = {x['request_id']: x for x in load(answers_dir / 'answers.json')}
    requests = load(columns / 'requests.json')
    assert len(answers) == len(requests) == build['requests']
    records = {x['page_id']: x for x in load(columns / 'records.json')}
    modules = ['source_column_runtime_v4.py', 'source_column_runtime_api.py', 'source_column_views.py',
               'source_column_selector_v2.py', 'overlap_continuity.py', 'table_mechanisms.py']
    if a.consolidation:
        modules += ['native_column_consolidation_api.py', 'native_column_consolidation_v2.py', 'native_column_consolidation.py']
    frozen = {name: sha(ROOT / 'code/research' / name) for name in modules}
    gate_hash = sha(ROOT / 'scripts/source_column_request_gate_v1.py')
    out.mkdir(parents=True, exist_ok=False)
    for folder in ['predictions/raw', 'predictions/markdown', 'provenance']:
        (out / folder).mkdir(parents=True)
    counts, changed = collections.Counter(), []
    for page in load(pages):
        pid = page['id']
        rawpath, mdpath = native / 'raw' / (pid + '.json'), native / 'markdown' / (pid + '.md')
        original, current = load(rawpath), load(prior / 'predictions/raw' / rawpath.name)
        before = copy.deepcopy(current)
        provenance = load(prior / 'provenance' / rawpath.name)
        record = records[pid]
        assert record['native_raw_sha256'] == provenance['native_raw_sha256'] == sha(rawpath)
        assert record['image_sha256'] == provenance['image_sha256'] == sha(page['image'])
        assert provenance['candidate_raw_sha256'] == sha(prior / 'predictions/raw' / rawpath.name)
        origins = provenance['final_origins']
        assert len(origins) == len(current['blocks'])
        decisions = []
        if record['proposals']:
            with Image.open(page['image']) as image:
                image = image.convert('RGB')
                proposals = columns_api.propose_source_columns(image, original)
                assert len(proposals) == len(record['proposals'])
                lookup = {x['key']: x for t in record['proposals'] for x in t['inputs']}
                supplied = {}
                for t in proposals:
                    for x in t['inputs']:
                        q = lookup[x['key']]
                        assert (q['pixel_sha256'], q['size'], q['affine']) == (x['pixel_sha256'], list(x['image'].size), x['affine'])
                        supplied[x['key']] = answers[q['request_id']]
                stages = [('source_columns_v4', columns_api.apply_source_columns)]
                if a.consolidation:
                    stages.append(('native_column_consolidation_v2', consolidation_api.apply_native_column_consolidation))
                for name, function in stages:
                    result = function(image, original, mdpath.read_text(), proposals, supplied)
                    for d in result['provenance']:
                        d = copy.deepcopy(d)
                        idx = d['block_index']
                        slots = [i for i, origin in enumerate(origins) if origin == [idx]]
                        d.update(strategy=name, applied=False)
                        if d.get('selected'):
                            counts[name + '_selected'] += 1
                            if len(slots) == 1 and current['blocks'][slots[0]] == original['blocks'][idx]:
                                current['blocks'][slots[0]] = copy.deepcopy(result['raw']['blocks'][idx])
                                d.update(applied=True, final_index=slots[0])
                                counts[name + '_applied'] += 1
                            else:
                                d['composition_reason'] = 'source_block_changed_or_removed'
                                counts[name + '_conflicts'] += 1
                        decisions.append(d)
                counts['proposed'] += len(proposals)
        dest_raw, dest_md = out / 'predictions/raw' / rawpath.name, out / 'predictions/markdown' / mdpath.name
        if current != before:
            save(dest_raw, current)
            dest_md.write_text(json2md(current['blocks']))
            changed.append(pid)
        else:
            shutil.copyfile(prior / 'predictions/raw' / rawpath.name, dest_raw)
            shutil.copyfile(prior / 'predictions/markdown' / mdpath.name, dest_md)
        provenance.update(table_column_decisions=decisions,
                          prior_candidate_raw_sha256=sha(prior / 'predictions/raw' / rawpath.name),
                          candidate_raw_sha256=sha(dest_raw), candidate_markdown_sha256=sha(dest_md))
        save(out / 'provenance' / rawpath.name, provenance)
        counts['pages'] += 1
    assert counts['pages'] == len(records)
    assert sha(ROOT / 'scripts/source_column_request_gate_v1.py') == gate_hash
    assert frozen == {name: sha(ROOT / 'code/research' / name) for name in modules}
    order = load(prior / 'composition_receipt.json')['order'] + ['source_columns_v4']
    if a.consolidation:
        order.append('native_column_consolidation_v2')
    save(out / 'composition_receipt.json', dict(status='COMPLETE', order=order, counts=dict(counts),
          changed_pages=changed, source_code_sha256=frozen, runtime_GT=False,
          current_source_pixels_verified=True, column_request_gate_sha256=gate_hash, response_receipt_sha256=sha(answers_dir / 'receipt.json'),
          historical_answer_reuse=build.get('historical_answers', False)))
    print(json.dumps(dict(counts)))


if __name__ == '__main__':
    main()
