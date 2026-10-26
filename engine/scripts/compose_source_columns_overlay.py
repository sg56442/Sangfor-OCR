#!/usr/bin/env python3
"""Re-run frozen source-column decisions, then overlay unchanged native origins.

Regional responses must match current source pixels and the recorded native
input. This adapter is for a same-input combination; runtime selection never
uses GT, page labels, or a preselected winners list.
"""
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
import source_column_runtime_v4 as runtime


def load(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ['native', 'pages', 'combined', 'columns', 'out']:
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    native, pages, prior, columns, out = [Path(getattr(args, k)).resolve()
                                        for k in ['native', 'pages', 'combined', 'columns', 'out']]
    assert out.is_relative_to(ROOT)
    modules = ['source_column_runtime_v4.py', 'source_column_runtime_api.py', 'source_column_views.py',
               'source_column_selector_v2.py', 'overlap_continuity.py', 'table_mechanisms.py']
    frozen = {file: sha(ROOT / 'code/research' / file) for file in modules}
    recorded_native = Path(load(columns / 'scopes.json')['current1651']['native']).resolve()
    assert recorded_native == native
    records = {Path(x['page_evidence']).stem: x for x in load(columns / 'records.json') if x['scope'] == 'current1651'}
    answers = {x['request_id']: x for x in load(columns / 'reused_answers.json')}
    for gpu in [4, 5]:
        answers.update({x['request_id']: x for x in load(columns / ('inference_gpu' + str(gpu)) / 'answers.json')})
    out.mkdir(parents=True, exist_ok=False)
    for folder in ['predictions/raw', 'predictions/markdown', 'provenance']:
        (out / folder).mkdir(parents=True)
    counts, edits = collections.Counter(), []
    for page in load(pages):
        pid = page['id']
        rawpath = native / 'raw' / (pid + '.json')
        mdpath = native / 'markdown' / (pid + '.md')
        original = load(rawpath)
        current = load(prior / 'predictions/raw' / rawpath.name)
        provenance = load(prior / 'provenance' / rawpath.name)
        assert provenance['native_raw_sha256'] == sha(rawpath)
        assert provenance['candidate_raw_sha256'] == sha(prior / 'predictions/raw' / rawpath.name)
        origins = provenance['final_origins']
        assert len(origins) == len(current['blocks'])
        record = records[pid]
        supplied, decisions = {}, []
        if record['proposals']:
            lookup = {x['key']: x for t in record['proposals'] for x in t['inputs']}
            image = Image.open(page['image']).convert('RGB')
            assert provenance['image_sha256'] == sha(page['image'])
            proposals = runtime.propose_source_columns(image, original)
            assert len(proposals) == len(record['proposals'])
            for t in proposals:
                for x in t['inputs']:
                    q = lookup[x['key']]
                    assert q['pixel_sha256'] == x['pixel_sha256']
                    assert q['size'] == list(x['image'].size)
                    supplied[x['key']] = answers[q['request_id']]
            result = runtime.apply_source_columns(image, original, mdpath.read_text(), proposals, supplied)
            for decision in result['provenance']:
                decision = copy.deepcopy(decision)
                idx = decision['block_index']
                slots = [i for i, origin in enumerate(origins) if origin == [idx]]
                decision['applied'] = False
                if decision['selected']:
                    if len(slots) == 1 and current['blocks'][slots[0]] == original['blocks'][idx]:
                        current['blocks'][slots[0]] = copy.deepcopy(result['raw']['blocks'][idx])
                        decision.update(applied=True, final_index=slots[0])
                        counts['applied'] += 1
                    else:
                        decision['composition_reason'] = 'source_block_changed_or_removed'
                        counts['conflicts'] += 1
                decisions.append(decision)
            counts['proposed'] += len(proposals)
            counts['selected'] += sum(x['selected'] for x in decisions)
        before = load(prior / 'predictions/raw' / rawpath.name)
        dest_raw, dest_md = out / 'predictions/raw' / rawpath.name, out / 'predictions/markdown' / mdpath.name
        if current != before:
            save(dest_raw, current)
            dest_md.write_text(json2md(current['blocks']))
            edits.append(pid)
        else:
            shutil.copyfile(prior / 'predictions/raw' / rawpath.name, dest_raw)
            shutil.copyfile(prior / 'predictions/markdown' / mdpath.name, dest_md)
        provenance.update(source_columns_v4=decisions, prior_candidate_raw_sha256=sha(prior / 'predictions/raw' / rawpath.name),
                          candidate_raw_sha256=sha(dest_raw), candidate_markdown_sha256=sha(dest_md))
        save(out / 'provenance' / rawpath.name, provenance)
        counts['pages'] += 1
    assert counts['pages'] == len(records)
    assert frozen == {file: sha(ROOT / 'code/research' / file) for file in modules}
    save(out / 'composition_receipt.json', dict(status='COMPLETE', counts=dict(counts), changed_pages=edits,
         order=load(prior / 'composition_receipt.json')['order'] + ['source_columns_v4'],
         native=str(native), prior=str(prior), columns=str(columns), source_code_sha256=frozen,
         runtime_GT=False, new_model_calls=0, current_source_pixels_verified=True,
         scope='Same-input responses replay through frozen API; not independent end-to-end repeat'))
    print(json.dumps(dict(counts)))


if __name__ == '__main__':
    main()
