"""Bindings for the reviewed fragment and zero-call sizing final stages."""
import hashlib
import json
from pathlib import Path

from phase2_final_runtime_v1 import (
    ROOT, PYTHON, inside, load, save, sha, verify_hashes,
)


def fragment_binding(predictions, native_predictions, native_http, pages, output, budget, closure):
    """Match the immutable fragment-v3 runtime's input and installed-code binding."""
    predictions, native_predictions = Path(predictions).resolve(), Path(native_predictions).resolve()
    native_http, pages, output = Path(native_http).resolve(), Path(pages).resolve(), Path(output).resolve()
    inputs = {str(pages): sha(pages), str(native_http): sha(native_http)}
    for page in load(pages):
        for path in [predictions/'raw'/(page['id']+'.json'),
                     predictions/'markdown'/(page['id']+'.md'),
                     native_predictions/'raw'/(page['id']+'.json'), Path(page['image'])]:
            inputs[str(path.resolve())] = sha(path)
    binding = dict(input=str(predictions), native=str(native_predictions), pages=str(pages),
        out=str(output), budget=budget,
        inputs_sha256=hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
        closure_sha256=hashlib.sha256(json.dumps(closure, sort_keys=True).encode()).hexdigest())
    return binding, inputs


def prepare_fragment(plan, frozen):
    base, delivery = inside(plan['output']), inside(plan['delivery'])
    phase = load(ROOT/'control/phase2_plan.json')
    predictions, native = base/'B_dot/predictions', base/'native/predictions'
    pages, output = inside(frozen['pages']), base/'B_fragment'
    entry = inside(frozen['fragment_runner'])
    closure = frozen['fragment_source_hashes']
    verify_hashes(closure)
    binding, inputs = fragment_binding(predictions, native, base/'native/audit/http.jsonl',
        pages, output, frozen['fragment_budget'], closure)
    permit = delivery/'fragment_final_permit.json'
    argv_spec = delivery/'fragment_runtime_argv.json'
    assert not permit.exists() and not argv_spec.exists() and not output.exists()
    save(permit, dict(mode='final_validation', approved=True, approved_by='RSI',
        phase=phase['phase'], run_binding=binding, not_before=phase['final_start_at'],
        campaign_deadline=phase['deadline_at'], source_hashes=frozen['source_hashes']))
    save(delivery/'fragment_prepared_binding.json', dict(binding=binding, input_hashes=inputs))
    save(argv_spec, dict(entry_sha256=sha(entry), argv=[
        '--pages', str(pages), '--input', str(predictions), '--native', str(native),
        '--native-http', str(base/'native/audit/http.jsonl'), '--budget', str(frozen['fragment_budget']),
        '--out', str(output), '--permit', str(permit), '--permit-sha256', sha(permit)]))
    return [PYTHON, '-B', 'scripts/run_phase2_fragment_locked_v1.py', '--runtime-argv', str(argv_spec)]


def verify_sizing(folder, predictions):
    folder, predictions = Path(folder), Path(predictions)
    receipt = load(folder/'receipt.json')
    assert receipt['status'] == 'COMPLETE_DIAGNOSTIC_UNADOPTED'
    assert receipt['pages'] == 1651 and receipt['new_model_calls'] == receipt['auxiliary_observations'] == 0
    assert receipt['known_GT_hidden'] and receipt['network_isolated'] and not receipt['runtime_GT']
    assert Path(receipt['source']).resolve() == predictions.resolve()
    verify_hashes(receipt['source_hashes'])
    records = receipt['records']
    ids = {p.stem for p in (predictions/'raw').glob('*.json')}
    assert len(records) == len(ids) == 1651
    assert {r['page_evidence_only'] for r in records} == ids
    for sub, suffix in [('raw', 'json'), ('markdown', 'md')]:
        assert {p.stem for p in (folder/'predictions'/sub).glob('*.'+suffix)} == ids
        for record in records:
            name = record['page_evidence_only']+'.'+suffix
            assert sha(predictions/sub/name) == record['input_'+sub+'_sha256']
            assert sha(folder/'predictions'/sub/name) == record['output_'+sub+'_sha256']
    return receipt


def verify_fragment(folder, predictions, native_predictions, native_http, pages, frozen, final=True):
    folder = Path(folder)
    receipt, actual = load(folder/'receipt.json'), load(folder/'binding.json')
    assert receipt['status'] == 'COMPLETE'
    assert receipt['configured'] == frozen['fragment_budget']
    expected, inputs = fragment_binding(predictions, native_predictions, native_http, pages,
        folder, frozen['fragment_budget'], frozen['fragment_source_hashes'])
    assert actual['binding'] == expected and actual['input_hashes'] == inputs
    assert actual['source_hashes'] == frozen['fragment_source_hashes']
    verify_hashes(actual['source_hashes'])
    outputs = load(folder/'output_hashes.json')
    assert len(outputs) == 3302
    for name, digest in outputs.items():
        assert sha(folder/name) == digest
    wrapper = load(folder.parent/(folder.name+'.wrapper_receipt.json'))
    assert wrapper['status'] == 'COMPLETE' and wrapper['returncode'] == 0 and wrapper['GPU'] == '3'
    assert wrapper['runtime_entry_sha256'] == sha(inside(frozen['fragment_runner']))
    assert wrapper['wrapper_sha256'] == sha(ROOT/'scripts/run_phase2_fragment_locked_v1.py')
    from phase2_final_runtime_v1 import GT
    assert set(wrapper['known_GT_paths_hidden']) == {p for p in GT if Path(p).exists()}
    budget_path = folder/'transport_budget.json'
    budget = load(budget_path) if budget_path.exists() else dict(reserved=0, denied=0)
    assert budget['reserved'] <= frozen['fragment_budget'] and budget['denied'] == 0
    assert budget['reserved'] == receipt['consumed']
    audit_path = folder/'audit/http.jsonl'
    audit = [json.loads(line) for line in audit_path.read_text().splitlines()] if audit_path.exists() else []
    configured = [r for r in audit if r['stage'] == 'configured']
    consumed = [r for r in audit if r['stage'] == 'consumed']
    assert len(configured) == len(consumed) == budget['reserved']
    assert all(r['response']['model'] == frozen['model'] for r in consumed)
    for key in ['prompt_tokens', 'completion_tokens', 'total_tokens']:
        assert receipt['usage'][key] == sum(r['response']['usage'][key] for r in consumed)
    if budget['reserved']:
        service = load(folder/'service_binding.json')
        assert service['model'] == frozen['model']
        assert service['container_id'] == frozen['services']['3']['container_id']
    if final:
        assert folder.name == 'B_fragment'
        permit = load(inside(frozen['_delivery'])/'fragment_final_permit.json')
        assert permit['run_binding'] == expected
        assert wrapper['argv_spec_sha256'] == sha(inside(frozen['_delivery'])/'fragment_runtime_argv.json')
    return dict(actual_attempts=budget['reserved'], extra_prompt_tokens=receipt['usage']['prompt_tokens'],
        extra_completion_tokens=receipt['usage']['completion_tokens'],
        triggered=receipt['triggered'], selected=receipt['selected'], applied=receipt['applied'],
        wall_seconds=receipt['wall_seconds'], GPU_busy_seconds=None,
        time_definition='Runtime wall time; GPU active time not separately measured')
