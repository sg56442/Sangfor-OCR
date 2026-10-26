"""Prepare a bound final panel run and verify all observations/composed outputs."""
import collections
import copy
import json
from pathlib import Path
import sys

from phase2_final_runtime_v1 import ROOT, PYTHON, inside, load, save, sha, verify_hashes


def prepare_panel(plan, frozen, source):
    sys.path.insert(0, str(ROOT/'code/experimenter'))
    from initialize_panel_0112_v2 import initialize
    out = inside(plan['output'])/'B_panel'
    pages = inside(frozen['pages'])
    initialize(pages, source, out, [int(plan['panel_gpu'])])
    request = load(out/'permit_request.json')
    # Local implementation must already belong to the accepted final freeze.
    for p, h in request['source_hashes'].items():
        path = Path(p)
        if path.is_relative_to(ROOT):
            assert frozen['source_hashes'].get(p, frozen['source_hashes'].get(str(path.relative_to(ROOT)))) == h, p
    phase = load(ROOT/'control/phase2_plan.json')
    permit = dict(request, approved=True, approved_by='RSI', phase=phase['phase'],
                  not_before=phase['final_start_at'], campaign_deadline=phase['deadline_at'])
    path = inside(plan['delivery'])/'panel_final_permit.json'
    assert not path.exists()
    save(path, permit)
    return [PYTHON, '-B', 'code/experimenter/execute_panel_0112_v2.py',
            '--manifest', str(pages), '--inputs', str(source), '--out', str(out),
            '--gpus', plan['panel_gpu'], '--final-permit', str(path),
            '--final-permit-sha256', sha(path)]


def verify_panel(folder, source, pages, plan=None, frozen=None):
    sys.path[:0] = [str(ROOT/'code/experimenter'), str(ROOT/'code/runtime')]
    from dependency_lock_0111_v1 import verify
    from panel_group_gate_0109_v1 import admit
    from compose_panels_0108_v2 import select
    from finite_request_identity_0101_v1 import prepare, pix, key, params, prompts
    from phase2_runtime_guard_v1 import MODEL, WEIGHT
    from PIL import Image

    folder, source, pages = Path(folder), Path(source), Path(pages)
    verify(folder/'dependencies.json')
    verify_hashes(load(folder/'freeze_transport_v2.json')['source_hashes'])
    census = load(folder/'census.json')
    assert census['pages'] == len(census['bindings']) == 1651
    expected_ids = {p['id'] for p in load(pages)}
    for rp, rh, image, ih, mp, mh in census['bindings']:
        assert Path(rp).parent.resolve() == (source/'raw').resolve()
        assert Path(mp).parent.resolve() == (source/'markdown').resolve()
        assert sha(rp) == rh and sha(image) == ih and sha(mp) == mh
    assert {Path(row[0]).stem for row in census['bindings']} == expected_ids
    if plan is not None:
        from panel_admission_0112_v2 import run_binding
        binding = run_binding(pages, source, folder, [int(plan['panel_gpu'])])
        assert load(folder/'admission_binding.json') == binding
        permit = load(inside(plan['delivery'])/'panel_final_permit.json')
        assert permit['approved'] and permit['approved_by'] == 'RSI' and permit['run_binding'] == binding
        assert load(folder/'final_permit.json') == permit
    budget = load(folder/'budget.json')
    assert budget['maximum'] == 24 and budget['reserved'] <= 24
    assert all(n <= 6 for n in budget['by_source'].values())
    assert len(budget['identities']) == len(set(budget['identities'])) == budget['reserved']
    costs = dict(actual_attempts=0, extra_prompt_tokens=0, extra_completion_tokens=0,
                 failed=0, non_stop_decodes=0, worker_seconds_sum=0.0)
    observations = []
    for worker in sorted(folder.glob('gpu*_attempt*')):
        execution = load(worker/'execution.json')
        assert execution['status'] in ['COMPLETE', 'COMPLETE_WITH_FAILURES']
        assert execution['GT_hidden'] and execution['retry'] == 0
        service = load(worker/'service.json')
        assert service['model'] == MODEL and service['weight_sha256'] == WEIGHT
        assert service['read_only_checkpoint_mount']
        assert load(worker/'dependency_preHTTP.json')['lock_sha256'] == sha(folder/'dependencies.json')
        if frozen is not None:
            gpu = worker.name.split('_')[0][3:]
            assert service['container_id'] == frozen['services'][gpu]['container_id']
        result_path = worker/'results.json'
        records = load(result_path) if result_path.exists() else []
        cost = load(worker/'cost.json')
        audit_path = worker/'audit/http.jsonl'
        audit = [json.loads(line) for line in audit_path.read_text().splitlines()] if audit_path.exists() else []
        consumed = {r['request_sha256']:r for r in audit if r['stage'] == 'consumed'}
        attempts = load(worker/'attempts.json') if (worker/'attempts.json').exists() else []
        assert cost['actual_HTTP'] == len(attempts)
        costs['actual_attempts'] += cost['actual_HTTP']
        costs['worker_seconds_sum'] += cost['wall_seconds']
        costs['failed'] += cost['failed']
        for label in ['prompt_tokens', 'completion_tokens']:
            actual = sum(r.get('response', {}).get('usage', {}).get(label, 0) for r in records)
            assert actual == cost[label]
            costs['extra_'+label] += actual
        for r in records:
            if r.get('consumed'):
                assert r['response']['model'] == MODEL
                assert consumed[r['request_sha256']]['response'] == r['response']
                c = census['records'][r['ordinal']]
                with Image.open(c['source']) as image:
                    prepared = prepare(image.convert('RGB').crop(r['rect']), r['task'])
                assert r['prepared_pixel_sha256'] == pix(prepared)
                assert r['identity_key'] == key(prepared.size, pix(prepared), r['task'])
                assert r['configured_parameters'] == params(r['task'])
                assert r['configured_prompts'] == prompts(r['task'])
                assert r['raw_sha256'] == c['raw_sha256'] and r['source_sha256'] == c['source_sha256']
                assert r['processor']['result']['prompt_tokens_match']
                costs['non_stop_decodes'] += not r['finished_normally']
        observations.extend(records)
    planned = []
    for phase in ['layout', 'recognition']:
        planned.extend(load(folder/f'plan_{phase}.json')['requests'])
    identity = lambda r: (r['task'], r['ordinal'], r['identity_key'])
    assert len(observations) == len(planned)
    assert sorted(map(identity, observations)) == sorted(map(identity, planned))
    assert costs['actual_attempts'] == budget['reserved']
    gates = {}
    for r in observations:
        if r['task'] != '[layout]':
            continue
        c = census['records'][r['ordinal']]
        with Image.open(c['source']) as image:
            eligible, reason = admit(r, c, image.convert('RGB').crop(c['rect']))
        gates[r['ordinal']] = dict(ordinal=r['ordinal'], eligible=eligible, evidence=reason)
    assert gates == {r['ordinal']:r for r in load(folder/'layout_binding.json')}
    edits = collections.defaultdict(list)
    for r in observations:
        if r['task'] != 'text':
            continue
        c = census['records'][r['ordinal']]
        raw = load(c['raw'])
        md = (source/'markdown'/Path(c['raw']).with_suffix('.md').name).read_text()
        edit, decision = select(c, r, raw, md)
        if edit and gates.get(r['ordinal'], {}).get('eligible'):
            edits[c['raw']].append(dict(edit, ordinal=c['ordinal'], source=c['source']))
    selection = load(folder/'selection.json')
    # Parallel worker ordering may differ; semantic edit ordering must agree.
    normalize = lambda d: {k:sorted(v, key=lambda r:r['ordinal']) for k,v in d.items()}
    assert normalize(edits) == normalize(selection['edits'])
    changed = []
    target = folder/'candidate/predictions'
    for kind, ext in [('raw', '.json'), ('markdown', '.md')]:
        assert {p.stem for p in (target/kind).glob('*'+ext)} == expected_ids
    for rp in sorted((source/'raw').glob('*.json')):
        mp = source/'markdown'/(rp.stem+'.md')
        rows = edits.get(str(rp.resolve()), [])
        if not rows:
            assert sha(rp) == sha(target/'raw'/rp.name)
            assert sha(mp) == sha(target/'markdown'/mp.name)
            continue
        raw, markdown = copy.deepcopy(load(rp)), mp.read_text()
        blocks = []
        for index, block in enumerate(raw['blocks']):
            blocks.append(block)
            for edit in sorted([r for r in rows if r['owner'] == index], key=lambda r:(r['rect'][1],r['rect'][0])):
                with Image.open(edit['source']) as image:
                    w, h = image.size
                blocks.append(dict(type='text', bbox=[v/(w if i%2 == 0 else h) for i,v in enumerate(edit['rect'])],
                    angle=0, content=edit['text'], merge_prev=False, source_panel_parent_index=index,
                    source_panel_relation='transcription_inside_preserved_image'))
        raw['blocks'] = blocks
        groups = collections.defaultdict(list)
        for edit in sorted(rows, key=lambda r:(r['owner'],r['rect'][1],r['rect'][0])):
            groups[edit['anchor']].append(edit['text'])
        for anchor, texts in groups.items():
            assert markdown.count(anchor) == 1
            markdown = markdown.replace(anchor, '\n\n'.join(texts)+'\n\n'+anchor, 1)
        assert raw == load(target/'raw'/rp.name)
        assert markdown == (target/'markdown'/mp.name).read_text()
        changed.append(rp.stem)
    assert changed == selection['changed_pages']
    assert selection['actual_HTTP'] == costs['actual_attempts']
    costs.update(changed_pages=len(changed), selected_blocks=sum(map(len, edits.values())),
                 extra_budget=24, retries=0, GPU_busy_seconds=None)
    return costs
