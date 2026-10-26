#!/usr/bin/env python3
"""Compose current-image local layout responses on exact unchanged block origins.

This is same-run response composition, not a fresh end-to-end repeat. Selection
is the frozen caller-current API; scores and annotations are never read.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import shutil
import sys

from PIL import Image
from mineru_vl_utils.post_process import json2md

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code/runtime'))
import layout_current_v1 as runtime


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def updated_origins(origins, records, family):
    if family == 'dense':
        return origins
    merged, removed = {}, set()
    for rec in records:
        if not rec['accepted']:
            continue
        for group in rec['selected_groups']:
            ids = group['indices']
            assert not removed.intersection(ids)
            merged[min(ids)] = sorted({v for i in ids for v in origins[i]})
            removed.update(ids)
    return [merged[i] if i in merged else old for i, old in enumerate(origins)
            if i in merged or i not in removed]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ['native', 'combined', 'group', 'dense', 'out']:
        p.add_argument('--' + key, required=True)
    a = p.parse_args()
    native, prior, group, dense, out = [Path(getattr(a, k)).resolve()
                                       for k in ['native', 'combined', 'group', 'dense', 'out']]
    assert out.is_relative_to(ROOT)
    modules = ['layout_current_v1.py', 'local_layout_apply_v1.py', 'layout_row_pairs_v1.py']
    frozen = {f: sha(ROOT / 'code/runtime' / f) for f in modules}
    families = {}
    for family, source in [('group', group), ('dense', dense)]:
        props = load(source / 'proposals.json')
        if family == 'group':
            # Expanded proposal version has its own pending evaluation.
            props = [x for x in props if x['stratum'] != 'expanded']
            answers = {x['proposal']: x['blocks'] for x in load(source / 'recognition.json')}
            requests = {x['proposal']: x for x in load(source / 'requests.json')}
        else:
            answers = {x['proposal_id']: load(source / 'inference/predictions/raw' /
                       ('p' + str(x['proposal_id']) + '.json'))['blocks'] for x in props}
            requests = {}
        by_page = collections.defaultdict(list)
        for prop in props:
            by_page[prop['page']].append(prop)
        families[family] = source, by_page, answers, requests

    out.mkdir(parents=True, exist_ok=False)
    for folder in ['predictions/raw', 'predictions/markdown', 'provenance']:
        (out / folder).mkdir(parents=True)
    counts, edits = collections.Counter(), []
    for rawpath in sorted((prior / 'predictions/raw').glob('*.json')):
        pid = rawpath.stem
        original_path = native / 'raw' / rawpath.name
        original = load(original_path)
        raw, provenance = load(rawpath), load(prior / 'provenance' / rawpath.name)
        assert provenance['native_raw_sha256'] == sha(original_path)
        assert provenance['candidate_raw_sha256'] == sha(rawpath)
        origins = provenance['final_origins']
        assert len(origins) == len(raw['blocks'])
        records = {}
        for family, (source, by_page, answers, requests) in families.items():
            props = by_page.get(pid, [])
            if not props:
                continue
            with Image.open(props[0]['source_image']) as opened:
                image = opened.convert('RGB')
            for prop in props:
                assert prop['source_native_sha256'] == sha(original_path)
                assert [runtime.signature(original['blocks'][i]) for i in prop['indices']] == prop['origin_signatures']
                assert runtime.pixel_hash(image) == prop['source_pixels_sha256']
                crop = source / ('p' + str(prop['proposal_id']) + '.png')
                with Image.open(crop) as opened:
                    assert runtime.pixel_hash(opened) == runtime.pixel_hash(image.crop(prop['pixel_rect']))
                if family == 'group':
                    assert sha(crop) == requests[prop['proposal_id']]['encoded_sha256']
                else:
                    assert sha(original_path) == sha(source / 'baseline/predictions/raw' / rawpath.name)
            before = raw['blocks']
            after, recs = runtime.select_and_apply(before, image, props, answers, family)
            for rec in recs:
                if rec['accepted']:
                    rec['native_origins'] = [origins[i] for g in rec['selected_groups'] for i in g['indices']]
            origins = updated_origins(origins, recs, family)
            assert len(origins) == len(after)
            raw['blocks'] = after
            records[family] = recs
            counts[family + '_proposed'] += len(props)
            counts[family + '_accepted'] += sum(x['accepted'] for x in recs)
            counts[family + '_conflicts'] += sum('stale' in x.get('reason', '') or 'conflict' in x.get('reason', '') for x in recs)
        dest_raw = out / 'predictions/raw' / rawpath.name
        mdpath = prior / 'predictions/markdown' / (pid + '.md')
        dest_md = out / 'predictions/markdown' / mdpath.name
        if raw != load(rawpath):
            save(dest_raw, raw)
            dest_md.write_text(json2md(raw['blocks']))
            edits.append(pid)
        else:
            shutil.copyfile(rawpath, dest_raw)
            shutil.copyfile(mdpath, dest_md)
        provenance.update(local_layout=records, final_origins=origins,
                          prior_candidate_raw_sha256=sha(rawpath),
                          candidate_raw_sha256=sha(dest_raw), candidate_markdown_sha256=sha(dest_md))
        save(out / 'provenance' / rawpath.name, provenance)
        counts['pages'] += 1
        counts['markdown_changed_vs_prior'] += dest_md.read_bytes() != mdpath.read_bytes()
    assert counts['pages'] == len(list((native / 'raw').glob('*.json')))
    assert frozen == {f: sha(ROOT / 'code/runtime' / f) for f in modules}
    save(out / 'composition_receipt.json', dict(status='COMPLETE', counts=dict(counts),
         order=load(prior / 'composition_receipt.json')['order'] + ['local_group_v1', 'rowpair_v1'],
         native=str(native), prior=str(prior), group=str(group), dense=str(dense),
         changed_pages=edits, source_code_sha256=frozen, current_input_identity_verified=True,
         runtime_GT=False, new_model_calls=0,
         scope='Frozen same-native current-image regional responses; not independent end-to-end acceptance'))
    print(json.dumps(dict(counts)))


if __name__ == '__main__':
    main()
