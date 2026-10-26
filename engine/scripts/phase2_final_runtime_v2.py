"""Bound final-run preparation; no inference, cached answers, or score selection."""
import ast
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
PYTHON = '/opt/p2t10/venv/bin/python'
GT = ['/opt/p2t10/hidden/OmniDocBench.json',
      '/opt/p2t10/hidden/source_validation_v2_references.jsonl',
      '/opt/p2t10/hidden/source_validation_v1_references.jsonl']


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def inside(path):
    path = (ROOT / path).resolve()
    assert path.is_relative_to(ROOT), path
    return path


def save(path, value):
    path = inside(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def verify_hashes(hashes):
    for path, expected in hashes.items():
        assert sha(ROOT / path) == expected, path


def pure_command(argv):
    hidden = [p for p in GT if Path(p).exists()]
    shell = ('set -euo pipefail\nn="$1"; shift\n'
             'for ((i=0;i<n;i++)); do mount --bind /dev/null "$1"; '
             'test ! -s "$1"; shift; done\nexec "$@"')
    return ['unshare', '--net', '--mount', '--propagation', 'private', '/bin/bash',
            '-c', shell, 'phase2-final-pure', str(len(hidden)), *hidden, *map(str, argv)]


@contextlib.contextmanager
def gpu_lock(gpu, deadline):
    path = ROOT / 'control/phase2_final_gpu_locks' / (str(gpu) + '.lock')
    path.parent.mkdir(exist_ok=True)
    with path.open('a+') as stream:
        while True:
            assert time.time() < deadline, 'Final deadline reached waiting for GPU'
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(1)
        yield


def final_permit(path, binding, frozen):
    phase = load(ROOT / 'control/phase2_plan.json')
    value = dict(mode='final_validation', approved=True, approved_by='RSI',
                 phase=phase['phase'], run_binding=binding,
                 not_before=phase['final_start_at'], campaign_deadline=phase['deadline_at'],
                 source_hashes=frozen['source_hashes'])
    assert not Path(path).exists()
    save(path, value)
    return ['--final-validation-admission', str(path), '--final-validation-sha256', sha(path)]


def static_lists(entry, names):
    result = {}
    for node in ast.walk(ast.parse(Path(entry).read_text())):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    result[target.id] = ast.literal_eval(node.value)
    assert set(result) == set(names)
    return result


def prepare_b(plan, frozen, dependency_snapshot):
    """Bind this repeat's future native path and current immutable core code."""
    delivery = inside(plan['delivery'])
    delivery.mkdir(parents=True, exist_ok=False)
    entry = inside(frozen['b_runner'])
    names = static_lists(entry, ['efficient_files', 'column_gate_files'])
    rules = inside(frozen['rules_freeze'])
    extra = dict(load(rules)['source_hashes'])
    extra[str(rules)] = sha(rules)
    runner = ROOT / 'code/research/run_native_rules_track_a_v1.py'
    extra[str(runner)] = sha(runner)
    native, core, pages = inside(plan['output'])/'native', inside(plan['b_output']), inside(frozen['pages'])
    admission = dict(approved=True, entry_sha256=sha(entry),
        native_auditor_sha256=sha(ROOT/'scripts/audit_single_model_inputs_v1.py'),
        cost_tool_sha256=sha(ROOT/'scripts/summarize_single_model_cost_v1.py'),
        column_gate_hashes={p: sha(ROOT/p) for p in names['column_gate_files']},
        efficiency_source_hashes={p: sha(ROOT/'code/experimenter'/p) for p in names['efficient_files']},
        pages_sha256=sha(pages), gpu=plan['b_gpu'], table_columns=frozen['table_columns'],
        max_extra_requests=frozen['maximum_extra_requests'], max_dense_tiles=frozen['maximum_dense_tiles'],
        score=False, native_run=str(native), dependency_snapshot=dependency_snapshot,
        freeze_sha256=sha(inside(frozen['b_freeze'])), phase2_source_hashes=extra)
    admission_path = delivery/'b_admission.json'
    save(admission_path, admission)
    binding = dict(kind='B_core', input_admission_sha256=sha(admission_path), out=str(core),
        gpu=plan['b_gpu'], budget=frozen['maximum_extra_requests'],
        max_dense_tiles=frozen['maximum_dense_tiles'], native_run=str(native), pages_sha256=sha(pages))
    flags = final_permit(delivery/'b_final_permit.json', binding, frozen)
    argv = [PYTHON, '-B', str(entry), '--execute', '--admission', str(admission_path),
        '--pages', str(pages), '--native-run', str(native), '--out', str(core), '--gpu', plan['b_gpu'],
        '--table-columns', frozen['table_columns'], '--no-score', '--freeze-name', Path(frozen['b_freeze']).name,
        '--max-extra-requests', str(frozen['maximum_extra_requests']),
        '--max-dense-tiles', str(frozen['maximum_dense_tiles']), *flags]
    save(delivery/'core_spec.json', dict(argv=argv))
    return [PYTHON, '-B', str(inside(frozen['b_pipeline_runner'])),
        '--core', str(core), '--native', str(native), '--pages', str(pages),
        '--out', str(core)+'_tail', '--receipt', str(delivery/'b_execution.json'),
        '--core-spec', str(delivery/'core_spec.json')]


def prepare_grid(plan, frozen):
    """Bind actual current B+math predictions after they exist; never historical answers."""
    base = inside(plan['output'])
    predictions = base/'B_math/predictions'
    receipt = load(base/'B_math/receipt.json')
    assert receipt['status'] == 'COMPLETE' and receipt['pages'] == 1651 and receipt['extra_calls'] == 0
    native_receipt = base/'native/predictions/worker_receipt.json'
    n = load(native_receipt)
    assert n['is_complete'] and n['processed_count'] == 1651
    assert n['model'] == frozen['model'] and n['model_weight_sha256'] == frozen['weight_sha256']
    pages_path = inside(frozen['pages'])
    pages = load(pages_path)
    files = [*predictions.glob('raw/*.json'), *predictions.glob('markdown/*.md'),
             pages_path, *[Path(p['image']) for p in pages]]
    admission = dict(scope='pure_same_model_B_optional_math', model=frozen['model'],
        weight_sha256=frozen['weight_sha256'], source_hashes=frozen['source_hashes'],
        predictions=str(predictions), pages=str(pages_path), page_count=1651,
        input_hashes={str(p): sha(p) for p in files},
        provenance=dict(native=str(native_receipt), native_sha256=sha(native_receipt),
                        B_math_receipt=str(base/'B_math/receipt.json'),
                        B_math_sha256=sha(base/'B_math/receipt.json')))
    delivery = inside(plan['delivery'])
    path = delivery/'grid_admission.json'
    assert not path.exists()
    save(path, admission)
    output = inside(plan['grid_output'])
    binding = dict(kind='closed_grid', input_admission_sha256=sha(path), out=str(output),
                   gpu=plan['grid_gpu'], budget=frozen['grid_budget'])
    flags = final_permit(delivery/'grid_final_permit.json', binding, frozen)
    return [PYTHON, '-B', str(inside(frozen['grid_runner'])), '--admission', str(path),
            '--out', str(output), '--gpu', plan['grid_gpu'], '--budget', str(frozen['grid_budget']), *flags]
