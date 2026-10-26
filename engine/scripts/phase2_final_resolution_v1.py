"""Current-input bindings and audit for the finite same-MinerU resolution stage."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

from phase2_final_runtime_v1 import ROOT, PYTHON, inside, load, save, sha, verify_hashes
from phase2_resolution_runtime_v2 import final_binding, digest, binding_key


def prepare_resolution(plan, frozen):
    base, delivery = inside(plan['output']), inside(plan['delivery'])
    phase = load(ROOT/'control/phase2_plan.json')
    args = SimpleNamespace(predictions=(base/'B_before_resolution/predictions').resolve(),
        native=(base/'native').resolve(), pages=inside(frozen['pages']), out=base/'B_resolution',
        gpu=plan['resolution_gpu'], budget=frozen['resolution_budget'])
    binding, inputs = final_binding(args)
    permit = delivery/'resolution_final_permit.json'
    assert not permit.exists() and not args.out.exists()
    save(permit, dict(mode='final_validation', approved=True, approved_by='RSI',
        phase=phase['phase'], run_binding=binding, not_before=phase['final_start_at'],
        campaign_deadline=phase['deadline_at'], source_hashes=frozen['source_hashes']))
    save(delivery/'resolution_prepared_binding.json', dict(binding=binding, input_hashes=inputs))
    return [PYTHON, '-B', frozen['resolution_runner'], '--mode', 'run',
        '--predictions', str(args.predictions), '--native', str(args.native),
        '--pages', str(args.pages), '--out', str(args.out), '--gpu', args.gpu,
        '--budget', str(args.budget), '--final-permit', str(permit),
        '--final-permit-sha256', sha(permit)]


def verify_resolution(folder, predictions, native, pages, frozen, final=True, gpu=None):
    folder, predictions, native, pages = map(Path, [folder, predictions, native, pages])
    receipt, identity = load(folder/'receipt.json'), load(folder/'identity.json')
    assert receipt['status'] == 'COMPLETE' and receipt['failures'] == receipt['retry'] == 0
    assert Path(receipt['native']).resolve() == native.resolve()
    assert Path(receipt['predictions_input']).resolve() == predictions.resolve()
    assert Path(receipt['predictions_output']).resolve() == (folder/'predictions').resolve()
    assert receipt['model_sha256'] == frozen['weight_sha256']
    provenance = identity['provenance']
    assert receipt['input_identity'] == identity['input_identity'] == digest(provenance)
    assert provenance['pages_sha256'] == sha(pages)
    assert provenance['native_http_sha256'] == sha(native/'audit/http.jsonl')
    verify_hashes(provenance['code_sha256'])
    for row in provenance['inputs']:
        for kind in ['raw', 'markdown', 'source']:
            assert sha(row[kind]) == row[kind+'_sha256']
    manifest = load(pages)
    ids = {p['id'] for p in manifest}
    assert len(manifest) == len(ids) == len(provenance['inputs']) == 1651
    plans = load(folder/'processor_plan.json')
    admitted = [r for r in plans if r['admitted']]
    ledger = load(folder/'ledger.json') if (folder/'ledger.json').exists() else {}
    assert receipt['admitted'] == len(admitted)
    assert {r['request_key'] for r in admitted} == set(ledger)
    assert receipt['unique_requests'] == receipt['completed'] == len(ledger)
    budget = load(folder/'transport_budget.json')
    assert receipt['actual_HTTP'] == budget['reserved'] == len(ledger)
    assert budget['denied'] == 0 and budget['reserved'] <= budget['maximum']
    logs = [json.loads(line) for line in (folder/'audit/http.jsonl').read_text().splitlines()] if ledger else []
    configured = {r['request_sha256']:r for r in logs if r['stage'] == 'configured'}
    consumed = {r['request_sha256']:r for r in logs if r['stage'] == 'consumed'}
    assert len(configured) == len(consumed) == len(ledger)
    assert set(configured) == set(consumed)
    for key, value in ledger.items():
        assert value['state'] == 'COMPLETE' and value['finish'] == 'stop'
        request = value['actual_request_sha256']
        assert binding_key(configured[request]) == key
        assert configured[request]['parameters']['model'] == frozen['model']
        assert consumed[request]['response']['model'] == frozen['model']
        assert consumed[request]['response']['usage'] == value['usage']
    for row in admitted:
        value = ledger[row['request_key']]
        request = configured[value['actual_request_sha256']]
        assert request['parameters'] == row['native_HTTP']['parameters']
        assert row['native_HTTP_exact_bound'] and row['processor_admitted']
        assert value['usage']['prompt_tokens'] == row['processor']['candidate']['prompt_tokens']
    for key in ['prompt_tokens', 'completion_tokens', 'total_tokens']:
        assert receipt['usage'][key] == sum(r['response']['usage'][key] for r in consumed.values())
    service = load(folder/'service_binding.json')
    assert service['model'] == frozen['model'] and service['weight_sha256'] == frozen['weight_sha256']
    assert service['container_id'] in {v['container_id'] for v in frozen['services'].values()}
    if gpu is not None:
        assert service['container_id'] == frozen['services'][gpu]['container_id']
    replays = load(folder/'replay.json')
    assert len(replays) == len(admitted)
    by_page = {}
    for row in replays:
        by_page.setdefault(row['page_io'], []).append(row)
    for sub, suffix in [('raw', '.json'), ('markdown', '.md')]:
        assert {p.stem for p in (folder/'predictions'/sub).glob('*'+suffix)} == ids
    for page in manifest:
        name = page['id']
        raw = load(predictions/'raw'/(name+'.json'))
        md = (predictions/'markdown'/(name+'.md')).read_text()
        for row in by_page.get(name, []):
            assert raw['blocks'][row['index']]['content'] == row['old']
            assert row['request_key'] in ledger
            if row['applied']:
                assert row['decision']['accepted'] and row['binding'] and md.count(row['old']) == 1
                raw['blocks'][row['index']]['content'] = row['new']
                md = md.replace(row['old'], row['new'], 1)
        assert load(folder/'predictions/raw'/(name+'.json')) == raw
        assert (folder/'predictions/markdown'/(name+'.md')).read_text() == md
    if final:
        assert gpu is not None and budget['maximum'] == frozen['resolution_budget']
        binding, inputs = final_binding(SimpleNamespace(predictions=predictions.resolve(),
            native=native.resolve(), pages=pages.resolve(), out=folder.resolve(), gpu=gpu,
            budget=frozen['resolution_budget']))
        recorded = load(folder/'runtime_binding.json')
        permit_path = inside(frozen['_delivery'])/'resolution_final_permit.json'
        assert recorded['binding'] == load(permit_path)['run_binding'] == binding
        assert recorded['input_hashes'] == inputs
        assert recorded['final_permit_sha256'] == sha(permit_path)
    return dict(actual_attempts=receipt['actual_HTTP'],
        extra_prompt_tokens=receipt['usage']['prompt_tokens'],
        extra_completion_tokens=receipt['usage']['completion_tokens'],
        triggered=len(plans), admitted=receipt['admitted'], applied=receipt['changed_blocks'],
        preflight_seconds=load(folder/'preflight.json')['wall_seconds'],
        execute_seconds=receipt['wall_seconds_this_execute'], GPU_busy_seconds=None,
        time_definition='CPU preflight and execute wall seconds measured separately; queue and GPU busy time not inferred.')


def verify_retention(folder, baseline, candidate, pages):
    folder, baseline, candidate, pages = map(Path, [folder, baseline, candidate, pages])
    receipt = load(folder/'receipt.json')
    assert receipt['pages'] == 1651 and receipt['model_calls'] == 0
    assert receipt['known_GT_hidden'] and receipt['network_isolated'] and not receipt['runtime_GT']
    assert Path(receipt['baseline']).resolve() == baseline.resolve()
    assert Path(receipt['candidate']).resolve() == candidate.resolve()
    assert receipt['pages_sha256'] == sha(pages)
    verify_hashes(receipt['input_hashes'])
    verify_hashes(receipt['source_hashes'])
    records = receipt['records']
    ids = {p['id'] for p in load(pages)}
    assert len(records) == len(ids) == 1651
    assert {r['page_evidence_only'] for r in records} == ids
    for sub, suffix in [('raw', '.json'), ('markdown', '.md')]:
        assert {p.stem for p in (folder/'predictions'/sub).glob('*'+suffix)} == ids
        for row in records:
            assert sha(folder/'predictions'/sub/(row['page_evidence_only']+suffix)) == row[sub+'_sha256']
    return receipt
