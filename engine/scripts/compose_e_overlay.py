#!/usr/bin/env python3
"""Apply frozen current-run E columns to unchanged source blocks in a combination.

Page locators identify artifacts only. Selection consumes current OCR columns,
never scores, annotations, source names or cached answers from another run.
"""
import argparse
import collections
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code/runtime'))
import column_signature_v1
from mineru_vl_utils.post_process import json2md


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ['native', 'combined', 'e', 'out']:
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    native, combined, eroot, out = [Path(getattr(args, key)).resolve()
                                  for key in ['native', 'combined', 'e', 'out']]
    assert out.is_relative_to(ROOT)
    code_hash = sha(column_signature_v1.__file__)
    identities = {x['page_locator']: x for x in load(eroot / 'current_native_identity.json')}
    answers = collections.defaultdict(dict)
    requests = load(eroot / 'requests.json')
    recognition = load(eroot / 'recognition.json')
    assert len(requests) == len(recognition)
    for request, answer in zip(requests, recognition):
        for key in ['proposal', 'kind', 'image', 'encoded_sha256']:
            assert request[key] == answer[key], key
        assert sha(request['image']) == request['encoded_sha256']
        assert answer['kind'] not in answers[answer['proposal']]
        answers[answer['proposal']][answer['kind']] = answer
    by_page = collections.defaultdict(list)
    for index, proposal in enumerate(load(eroot / 'proposals.json')):
        group = answers[index]
        keys = sorted((k for k in group if k.startswith('col')), key=lambda k: int(k[3:]))
        assert len(keys) == len(proposal['cuts']) - 1
        content, receipt = column_signature_v1.assemble([group[k]['content'] for k in keys])
        by_page[proposal['page']].append((proposal, content, receipt))
    out.mkdir(parents=True, exist_ok=False)
    for folder in ['predictions/raw', 'predictions/markdown', 'provenance']:
        (out / folder).mkdir(parents=True)
    counts = collections.Counter()
    changed_pages = []
    for pid, identity in identities.items():
        rawpath, mdpath = native / 'raw' / (pid + '.json'), native / 'markdown' / (pid + '.md')
        assert sha(rawpath) == identity['raw_sha256']
        assert sha(mdpath) == identity['markdown_sha256']
        original = load(rawpath)
        raw = load(combined / 'predictions/raw' / rawpath.name)
        provenance = load(combined / 'provenance' / rawpath.name)
        assert provenance['native_raw_sha256'] == sha(rawpath)
        assert provenance['candidate_raw_sha256'] == sha(combined / 'predictions/raw' / rawpath.name)
        origins = provenance['final_origins']
        assert len(origins) == len(raw['blocks'])
        records, changed = [], False
        for proposal, content, receipt in by_page[pid]:
            original_index = proposal['index']
            source = original['blocks'][original_index]
            assert source['bbox'] == proposal['bbox']
            assert source.get('content', '') == proposal['native_content']
            targets = [i for i, origin in enumerate(origins) if origin == [original_index]]
            rec = dict(receipt, original_index=original_index, applied=False)
            if content is not None:
                if len(targets) != 1 or raw['blocks'][targets[0]] != source:
                    rec['reason'] = 'source_block_changed_or_removed'
                    counts['conflicts'] += 1
                else:
                    raw['blocks'][targets[0]]['content'] = content
                    rec.update(applied=True, final_index=targets[0])
                    changed = True
                    counts['e_applied'] += 1
                    # Reproduce the role's independent frozen E application.
                    expected = load(eroot / 'applied/selected/raw' / rawpath.name)['blocks'][original_index]
                    assert raw['blocks'][targets[0]] == expected
            records.append(rec)
        dst_raw, dst_md = out / 'predictions/raw' / rawpath.name, out / 'predictions/markdown' / mdpath.name
        if changed:
            save(dst_raw, raw)
            dst_md.write_text(json2md(raw['blocks']))
            changed_pages.append(pid)
        else:
            shutil.copyfile(combined / 'predictions/raw' / rawpath.name, dst_raw)
            shutil.copyfile(combined / 'predictions/markdown' / mdpath.name, dst_md)
        provenance.update(e=records, prior_candidate_raw_sha256=provenance['candidate_raw_sha256'],
                          candidate_raw_sha256=sha(dst_raw), candidate_markdown_sha256=sha(dst_md))
        save(out / 'provenance' / rawpath.name, provenance)
        counts['pages'] += 1
        counts['markdown_changed_vs_native'] += dst_md.read_bytes() != mdpath.read_bytes()
        counts['markdown_changed_vs_prior'] += dst_md.read_bytes() != (combined / 'predictions/markdown' / mdpath.name).read_bytes()
    assert len(list((combined / 'predictions/raw').glob('*.json'))) == len(identities)
    assert code_hash == sha(column_signature_v1.__file__)
    save(out / 'composition_receipt.json', dict(status='COMPLETE', counts=dict(counts),
         order=load(combined / 'composition_receipt.json')['order'] + ['E'],
         native=str(native), prior=str(combined), e=str(eroot), changed_pages=changed_pages,
         current_input_identity_verified=True, frozen_e_application_parity=True,
         selector_sha256=code_hash, runtime_GT=False, new_model_calls=0,
         scope='Same-current-native response composition, not independent end-to-end inference'))
    print(json.dumps(dict(counts)))


if __name__ == '__main__':
    main()
