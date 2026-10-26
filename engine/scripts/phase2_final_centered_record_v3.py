"""Final zero-call source-band grouping, input permits and complete reconstruction."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import time
from bs4 import BeautifulSoup
from phase2_final_runtime_v1 import ROOT, PYTHON, inside, load, save, sha, now, verify_hashes
sys.path.insert(0, str(ROOT/'code/research'))
from centered_runtime_0071_v4 import transform, dependencies, LazyImage

RUNNER = 'code/research/centered_runtime_0071_v4.py'


def binding(source, pages, budget):
    source, pages = Path(source).resolve(), Path(pages).resolve()
    assert source.is_relative_to(ROOT) and 0 <= budget <= 8
    manifest = load(pages)
    assert len(manifest) == len({p['id'] for p in manifest}) == 1651
    locked = {str(pages): sha(pages)}
    for p in manifest:
        for sub, ext in [('raw', '.json'), ('markdown', '.md')]:
            path = source/sub/(p['id']+ext)
            locked[str(path)] = sha(path)
        locked[p['image']] = sha(p['image'])
    return locked, dict(inputs=str(source), manifest_sha256=sha(pages), dependencies=dependencies(),
        input_binding_sha256=hashlib.sha256(json.dumps(locked, sort_keys=True).encode()).hexdigest(),
        budget=budget, HTTP=0)


def prepare(plan, frozen, track):
    assert track in ['A', 'B'] and frozen['centered_runner'] == RUNNER
    began = time.monotonic()
    out = inside(plan['output'])
    source, output = out/(track+'_before_centered/predictions'), out/('B_before_skew' if track == 'B' else 'A_before_column_bridge')
    assert not output.exists()
    pages = inside(frozen['pages'])
    _, request = binding(source, pages, frozen['centered_budget'])
    assert request['dependencies'] == load(inside(frozen['centered_dependencies']))
    phase, control = load(ROOT/'control/phase2_plan.json'), load(ROOT/'control/final_validation_plan.json')
    assert control['enabled'] and control['runtime_freeze'] == plan['freeze']
    assert control['runtime_freeze_sha256'] == plan['freeze_sha256']
    current = dt.datetime.now(dt.timezone.utc)
    assert dt.datetime.fromisoformat(control['start_at']) <= current < dt.datetime.fromisoformat(phase['deadline_at'])
    permit = out/(track+'_centered_permit.json')
    assert not permit.exists()
    save(permit, dict(approved=True, approved_by='RSI', run_binding=request,
        not_before=control['start_at'], expires_at=phase['deadline_at'],
        planned_output=str(output), plan_sha256=sha(inside(plan['_plan_path'])),
        freeze_sha256=plan['freeze_sha256'], zero_model_calls=True))
    save(out/(track+'_centered_prepare.json'), dict(at=now(), seconds=time.monotonic()-began,
         permit_sha256=sha(permit), run_binding=request))
    return [PYTHON, '-B', RUNNER, '--inputs', str(source), '--pages', str(pages),
            '--out', str(output), '--budget', str(frozen['centered_budget']), '--permit', str(permit)]


def verify(source, output, pages, *, frozen=None, plan=None, track=None):
    began = time.monotonic()
    source, output, pages = [Path(p).resolve() for p in [source, output, pages]]
    receipt = load(output/'receipt.json')
    budget = receipt['request_binding']['budget']
    locked, request = binding(source, pages, budget)
    assert receipt['inputs'] == str(source) and receipt['pages_manifest_sha256'] == sha(pages)
    assert receipt['pages'] == 1651 and receipt['HTTP'] == 0 and receipt['GT_hidden'] and receipt['network_disabled']
    assert request == receipt['request_binding'] and locked == load(output/'input_binding.json')
    assert request['dependencies'] == load(output/'dependencies.json')
    verify_hashes(request['dependencies'])
    if frozen is not None:
        assert request['dependencies'] == load(inside(frozen['centered_dependencies']))
        assert budget == frozen['centered_budget'] and receipt['production_permit_used']
        assert plan is not None and track in ['A', 'B']
        permit_path = inside(plan['output'])/(track+'_centered_permit.json')
        permit = load(permit_path)
        assert permit['approved'] and permit['approved_by'] == 'RSI' and permit['run_binding'] == request
        assert permit['planned_output'] == str(output) and permit['freeze_sha256'] == plan['freeze_sha256']
        assert permit['plan_sha256'] == sha(inside(plan['_plan_path']))
    records, changed, owners = [], [], 0
    for index, p in enumerate(load(pages)):
        rp, mp = source/'raw'/(p['id']+'.json'), source/'markdown'/(p['id']+'.md')
        rb, md = rp.read_bytes(), mp.read_bytes()
        image = LazyImage(p['image'])
        nr, nm, decisions = transform(rb, md, image)
        image.close()
        count = sum(r['applied'] for r in decisions)
        if count > 4 or owners+count > budget:
            nr, nm, count = rb, md, 0
            for r in decisions:
                if r['applied']: r.update(applied=False, reason='page_or_global_budget')
        owners += count
        if count: changed.append(index)
        records.append(dict(manifest_index=index, decisions=decisions))
        for kind, path, expected in [('raw', rp, nr), ('markdown', mp, nm)]:
            target = output/'predictions'/kind/path.name
            assert target.is_file() and not target.is_symlink() and target.read_bytes() == expected
        if count:
            before, after = json.loads(rb), json.loads(nr)
            assert len(before['blocks']) == len(after['blocks'])
            for b, a in zip(before['blocks'], after['blocks']):
                if b == a: continue
                assert {k:v for k,v in b.items() if k!='content'} == {k:v for k,v in a.items() if k!='content'}
                assert BeautifulSoup(b['content'], 'html.parser').get_text() == BeautifulSoup(a['content'], 'html.parser').get_text()
    assert records == receipt['records'] and changed == receipt['changed_pages'] and owners == receipt['changed_owners']
    assert all(len(list((output/'predictions'/sub).iterdir())) == 1651 for sub in ['raw', 'markdown'])
    return dict(pages=1651, changed_pages=changed, changed_owners=owners, new_HTTP=0,
                receipt_sha256=sha(output/'receipt.json'), replay_seconds=receipt['wall_seconds'],
                verification_seconds=time.monotonic()-began)


if __name__ == '__main__':
    results = {}
    for label in ['A_first', 'B_first', 'A_second', 'B_second']:
        output = ROOT/f'reports/researcher_phase2_0071/lazy_{label}'
        r = load(output/'receipt.json')
        results[label] = verify(r['inputs'], output, r['pages_manifest'])
        prior = ROOT/f'reports/researcher_phase2_0071/four_{label}/predictions'
        assert all(p.read_bytes() == (prior/sub/p.name).read_bytes()
                   for sub in ['raw', 'markdown'] for p in (output/'predictions'/sub).iterdir())
    report = dict(status='PASS_ALL_FOUR_FINAL_RUNTIME_RECONSTRUCTIONS', at=now(), results=results,
                  HTTP=0, all_scored_output_bytes_equal=True, verifier_sha256=sha(Path(__file__)))
    target = ROOT/'reports/rsi_phase2_centered_final_runtime_verified_v1.json'
    assert not target.exists()
    save(target, report)
    print({k:dict(verification_seconds=r['verification_seconds'], replay_seconds=r['replay_seconds']) for k,r in results.items()})
