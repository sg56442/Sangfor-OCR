#!/usr/bin/env python3
"""Compose frozen strategies by block on one caller-supplied native run.

This reuses responses from that same run for a frozen-output comparison. It is
not an independent end-to-end inference run. No scoring data is read here.
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
sys.path[:0] = [str(ROOT/'code/research'), str(ROOT/'code/runtime')]
from PIL import Image
from mineru_vl_utils.post_process import json2md
from runtime_aec_api import apply_ae, apply_fraction
from native_typed_grid import apply as apply_typed
from g_v4 import select_and_apply


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')


def typed_with_origins(blocks, origins):
    result, decisions, changed = apply_typed(blocks)
    replaced, removed = {}, set()
    for d in decisions:
        if d['selected']:
            indices = d['indices']
            replaced[min(indices)] = sorted({k for i in indices for k in origins[i]})
            removed.update(indices)
    new_origins = [replaced.get(i, origin) for i, origin in enumerate(origins)
                   if i not in removed or i in replaced]
    assert len(new_origins) == len(result)
    for d in decisions:
        d['original_indices'] = sorted({k for i in d['indices'] for k in origins[i]})
    return result, new_origins, decisions, changed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native', required=True)
    p.add_argument('--pages', required=True)
    p.add_argument('--ae', required=True, help='Builder directory with proposals.json and requests.json')
    p.add_argument('--ae-answers', required=True)
    p.add_argument('--g', required=True, help='G current-run root with probe/ and boundary/')
    p.add_argument('--out', required=True)
    p.add_argument('--without-typed', action='store_true')
    a = p.parse_args()
    native, ae, groot, out = map(lambda x: Path(x).resolve(), [a.native, a.ae, a.g, a.out])
    assert out.is_relative_to(ROOT)
    pages = load(a.pages)
    assert len(pages) == len({x['id'] for x in pages})
    code_paths = sorted({Path(module.__file__).resolve() for module in list(sys.modules.values())
                         if getattr(module, '__file__', None)
                         and Path(module.__file__).resolve().is_relative_to(ROOT/'code')})
    code_hashes = {str(x.relative_to(ROOT)): sha(x) for x in code_paths}
    inputs = load(ae/'inputs.json')
    assert Path(inputs['native']).resolve() == native
    ae_proposals, ae_requests = load(ae/'proposals.json'), load(ae/'requests.json')
    ae_answers = {x['request_id']: x for x in load(a.ae_answers)}
    assert len(ae_answers) == len(ae_requests)
    for request in ae_requests:
        assert sha(request['image_path']) == request['file_sha256']
        assert ae_answers[request['request_id']]['http_receipt']
    ae_by_page = collections.defaultdict(list)
    for proposal in ae_proposals:
        ae_by_page[proposal['page_evidence']].append(proposal)
    identities = {x['page_diagnostic_only']: x for x in load(groot/'probe/current_native_identity.json')}
    gprops = load(groot/'boundary/proposals.json')
    ganswers = load(groot/'boundary/merged_recognition.json')
    g_by_page, ans_by_proposal = collections.defaultdict(list), collections.defaultdict(list)
    for i, proposal in enumerate(gprops):
        g_by_page[proposal['page']].append((i, proposal))
    checked_images = set()
    for answer in ganswers:
        image = answer['image']
        if image not in checked_images:
            assert sha(image) == answer['encoded_sha256'], image
            checked_images.add(image)
        ans_by_proposal[answer['proposal']].append(answer)
    out.mkdir(parents=True, exist_ok=False)
    for folder in ['predictions/raw', 'predictions/markdown', 'provenance']:
        (out/folder).mkdir(parents=True)
    counters, page_records = collections.Counter(), []
    for ordinal, page in enumerate(pages):
        pid = page['id']
        rawpath, mdpath = native/'raw'/f'{pid}.json', native/'markdown'/f'{pid}.md'
        native_raw, native_md = load(rawpath), mdpath.read_text()
        identity = identities[pid]
        assert sha(rawpath) == identity['raw_sha256'] and sha(mdpath) == identity['markdown_sha256']
        blocks = native_raw['blocks']
        active_ae = [p for p in ae_by_page[pid] if all(ae_answers[k].get('valid_candidate', True)
                     and ae_answers[k].get('html') for k in p['request_ids'])]
        invalid_ae = [p for p in ae_by_page[pid] if p not in active_ae]
        with Image.open(page['image']) as source_image:
            image = source_image.convert('RGB')
            blocks, origins, ae_decisions, ae_changed = apply_ae(image, blocks, active_ae, ae_answers)
            ae_decisions.extend({'rule': 'AE_V2', 'request_ids': p['request_ids'], 'original_indices':p['indices'],
                                 'selected': False, 'reason': 'invalid_consumed_candidate'} for p in invalid_ae)
            if a.without_typed:
                typed_decisions, typed_changed = [], False
            else:
                blocks, origins, typed_decisions, typed_changed = typed_with_origins(blocks, origins)
            blocks, c_decisions, c_changed = apply_fraction(image, blocks, origins)
        remapped_props, remapped_answers, conflicts = [], [], []
        origin_lookup = {origin[0]: i for i, origin in enumerate(origins) if len(origin) == 1}
        for gi, proposal in g_by_page[pid]:
            assert Path(proposal['page_image']).resolve() == Path(page['image']).resolve()
            original_index = proposal['index']
            original = native_raw['blocks'][original_index]
            assert proposal['bbox'] == original['bbox']
            assert proposal['native_content'] == original.get('content', '')
            idx = origin_lookup.get(original_index)
            if idx is None or blocks[idx] != original:
                conflicts.append({'proposal': gi, 'reason': 'source_block_changed_or_removed', 'original_index': original_index})
                continue
            local_index = len(remapped_props)
            remapped_props.append(dict(proposal, index=idx, original_index=original_index, global_proposal=gi))
            remapped_answers.extend(dict(answer, proposal=local_index) for answer in ans_by_proposal[gi])
        before_g = copy.deepcopy(blocks)
        blocks, g_receipt = select_and_apply(blocks, remapped_props, remapped_answers,
                                            {'raw_sha256': sha(rawpath), 'image_sha256': sha(page['image']),
                                             'same_current_run_candidates': True})
        accepted = {d['original_block_index'] for d in g_receipt['decisions'] if d['selected']}
        final_origins = [origin for i, origin in enumerate(origins) for _ in range(2 if i in accepted else 1)]
        assert len(final_origins) == len(blocks)
        # Untouched blocks must be exactly retained across formula insertion.
        j = 0
        for i, block in enumerate(before_g):
            if i in accepted:
                assert blocks[j]['type'] == blocks[j+1]['type'] == 'equation'
                j += 2
            else:
                assert blocks[j] == block
                j += 1
        changed = bool(ae_changed or typed_changed or c_changed or g_receipt['changed'])
        if changed:
            result = copy.deepcopy(native_raw)
            result['blocks'] = blocks
            save(out/'predictions/raw'/rawpath.name, result)
            (out/'predictions/markdown'/mdpath.name).write_text(json2md(blocks))
        else:
            shutil.copyfile(rawpath, out/'predictions/raw'/rawpath.name)
            shutil.copyfile(mdpath, out/'predictions/markdown'/mdpath.name)
        record = {'page_diagnostic_only': pid, 'native_raw_sha256': sha(rawpath),
                  'native_markdown_sha256': sha(mdpath), 'image_sha256': sha(page['image']),
                  'candidate_raw_sha256': sha(out/'predictions/raw'/rawpath.name),
                  'candidate_markdown_sha256': sha(out/'predictions/markdown'/mdpath.name),
                  'changed': changed, 'markdown_changed': mdpath.read_bytes() != (out/'predictions/markdown'/mdpath.name).read_bytes(),
                  'ae': ae_decisions, 'typed': typed_decisions, 'fraction': c_decisions,
                  'g': g_receipt, 'g_conflicts': conflicts, 'final_origins': final_origins}
        save(out/'provenance'/f'{pid}.json', record)
        counters.update(pages=1, raw_changed_pages=int(changed), markdown_changed_pages=int(record['markdown_changed']),
                        ae_selected=sum(d['selected'] for d in ae_decisions), typed_selected=sum(d['selected'] for d in typed_decisions),
                        fraction_cells=sum(d['selected'] for d in c_decisions), g_selected=g_receipt['selected'], g_conflicts=len(conflicts))
        if changed:
            page_records.append({k: record[k] for k in ['page_diagnostic_only', 'changed', 'markdown_changed', 'native_raw_sha256', 'candidate_raw_sha256']})
        if (ordinal+1) % 100 == 0:
            print(json.dumps(dict(counters)), flush=True)
    assert all(sha(ROOT/path) == value for path, value in code_hashes.items()), 'Source code changed during composition'
    save(out/'composition_receipt.json', {'status': 'COMPLETE', 'scope': 'current frozen predictions; not independent end-to-end',
         'native': str(native), 'ae': str(ae), 'ae_answers': str(Path(a.ae_answers).resolve()), 'g': str(groot),
         'order': ['AE', 'TYPED' if not a.without_typed else 'SKIP_TYPED', 'C', 'G'],
         'counts': dict(counters), 'changed_pages': page_records, 'code_sha256': code_hashes,
         'GT_runtime_inputs': False, 'new_model_calls': 0, 'scored': False})
    print(json.dumps(dict(counters)), flush=True)


if __name__ == '__main__':
    main()
