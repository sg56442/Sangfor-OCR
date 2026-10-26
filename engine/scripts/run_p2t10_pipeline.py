"""Sangfor-OCR inference pipeline: native parsing, deterministic post-processing, bounded
same-model re-reads and the final table-cell stage, with per-stage verification.

Input-image hash checks live in the entry point (infer.py --verify-images); this pipeline never
scores its output (scoring is done by the official OmniDocBench repository).
"""
import argparse
import concurrent.futures
import datetime as dt
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time

from phase2_final_runtime_v2 import (ROOT, PYTHON, inside, load, save, sha, now,
    verify_hashes, pure_command, gpu_lock, prepare_b, prepare_grid)
from phase2_final_additions_v1 import prepare_fragment, verify_fragment, verify_sizing
from phase2_final_resolution_v1 import prepare_resolution, verify_resolution, verify_retention
from phase2_final_labels_v1 import verify_labels
from phase2_final_dot_leaders_v2 import verify_dot_leaders
from phase2_final_atoms_v1 import verify_atoms
from phase2_final_quantity_v1 import verify_quantity
from phase2_final_panel_v1 import prepare_panel, verify_panel
from phase2_final_mixed_v1 import prepare_mixed, mixed_command, verify_mixed, materialize_mixed
from phase2_final_render_groups_v1 import verify_render_groups, RENDER_PYTHON
from phase2_final_parallel_lists_v1 import verify_parallel_lists
from phase2_final_inline_display_v1 import verify_inline_display
from phase2_final_sparse_footer_v1 import (prepare_sparse,sparse_command,verify_sparse,materialize_sparse,verify_footer,FOOTER)
from phase2_final_numeric_mode_v1 import (prepare_numeric, approve_numeric, verify_numeric, materialize_numeric, verify_mode, MODE)
from phase2_final_repeated_text_v1 import verify_repeated, RUNNER as REPEATED
from phase2_final_header_group_v1 import verify_header, RUNNER as HEADER
from phase2_final_mixed_prose_v1 import verify_prose, RUNNER as PROSE
from phase2_final_array_label_v1 import verify_array_label, RUNNER as ARRAY_LABEL
from phase2_final_brace_v1 import prepare_brace, verify_brace, materialize_brace
from phase2_final_shared_row_v1 import prepare_shared_row, approve_shared_row, verify_shared_row, materialize_shared_row, RUNNER as SHARED_ROW
from phase2_final_column_list_v1 import prepare_column, approve_column, verify_column, materialize as materialize_tail, RUNNER as COLUMN, LIST_RUNNER
from verify_phase2_zero_call_tails_v2 import verify_tail
from phase2_final_repeated_lines_v1 import verify_lines, RUNNER as REPEATED_LINES
from phase2_final_prose_recovery_v1 import prepare_prose_recovery, verify_prose_recovery
from phase2_final_semantic_tails_v2 import verify as verify_semantic_tails
from phase2_final_centered_record_v3 import prepare as prepare_centered, verify as verify_centered
from phase2_final_skew_v2 import prepare as prepare_skew, verify as verify_skew
from phase2_final_column_bridge_v2 import prepare as prepare_column_bridge, verify as verify_column_bridge
import sys as _sys
_sys.path.insert(0,str(ROOT/'code/experimenter'))
from empty_final_0149_v1 import prepare as prepare_empty, verify as verify_empty
from phase2_overlap_v1 import run_with_background


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    args = parser.parse_args()
    path = inside(args.plan)
    plan, plan_sha = load(path), sha(path)
    plan['_plan_path'] = str(path)
    freeze_path = inside(plan['freeze'])
    frozen = load(freeze_path)
    assert sha(freeze_path) == plan['freeze_sha256']
    control = load(ROOT/'control/final_validation_plan.json')
    assert control['enabled'] and control['runtime_freeze'] == plan['freeze']
    assert control['runtime_freeze_sha256'] == plan['freeze_sha256']
    phase = load(ROOT/'control/phase2_plan.json')
    deadline = dt.datetime.fromisoformat(phase['deadline_at']).timestamp()
    assert dt.datetime.fromisoformat(control['start_at']).timestamp() <= time.time() < deadline
    out, core = inside(plan['output']), inside(plan['b_output'])
    assert not core.exists()
    pages = inside(frozen['pages'])
    state = dict(status='STARTING', at=now(), repeat=plan['repeat'], GPU=plan['gpu'],
        B_GPU=plan['b_gpu'], grid_GPU=plan['grid_gpu'], plan=str(path.relative_to(ROOT)),
        plan_sha256=plan_sha, freeze=plan['freeze'], freeze_sha256=plan['freeze_sha256'],
        configured_pages=1651, native_generated_here=True, all_document_inference_same_weights=True,
        steps=[], scores={}, target=frozen['target'],
        native_execution_mode='fresh_native_in_pipeline')

    def write():
        state['updated_at'] = now()
        save(out/'pipeline.json', state)

    def verify(images=False):
        assert sha(path) == plan_sha and sha(freeze_path) == plan['freeze_sha256']
        assert sha(pages) == frozen['pages_sha256'] and len(load(pages)) == 1651
        verify_hashes(frozen['source_hashes'])
        assert time.time() < deadline

    def command(name, argv, scoring=False):
        held, began = None, time.monotonic()
        if scoring:
            locks = ROOT/'control/single_model_score_slots'
            locks.mkdir(exist_ok=True)
            while held is None:
                assert time.time() < deadline
                for i in range(frozen['maximum_concurrent_scores']):
                    candidate = (locks/(str(i)+'.lock')).open('a+')
                    try:
                        fcntl.flock(candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        held = candidate
                        break
                    except BlockingIOError:
                        candidate.close()
                if held is None:
                    time.sleep(1)
        admitted = time.monotonic()
        try:
            with (out/(name+'.log')).open('w') as stream:
                proc = subprocess.run(list(map(str, argv)), cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='',
                             OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2'))
            proc.check_returncode()
            return dict(name=name, returncode=proc.returncode, wall_seconds=time.monotonic()-admitted,
                        queue_seconds=admitted-began, argv=list(map(str, argv)))
        finally:
            if held is not None:
                held.close()

    def step(name, argv, gpu=None):
        verify()
        state['status'] = name.upper()+'_RUNNING'
        write()
        if gpu is None:
            result = command(name, argv)
        else:
            with gpu_lock(gpu, deadline):
                sys.path.insert(0, str(ROOT/'code/experimenter'))
                from phase2_runtime_guard_v1 import guard
                binding = guard(gpu)
                assert binding['container_id'] == frozen['services'][gpu]['container_id']
                save(out/(name+'_service.json'), binding)
                result = command(name, argv)
        state['steps'].append(result)
        write()

    def pure(name, script, *arguments):
        step(name, pure_command([PYTHON, '-B', script, *map(str, arguments)]))

    def validate_rules(folder):
        receipt = load(folder/'composition_receipt.json')
        assert receipt['status'] == 'COMPLETE' and receipt['counts']['pages'] == 1651
        assert receipt['model_calls'] == receipt['DB_calls'] == 0 and receipt['GT_hidden'] and not receipt['smoke']

    def math_dot(track, source, do_dot=True):
        pure(track+'_math', 'code/research/phase2_replay_math_prime_v1.py',
             '--predictions', source/'predictions', '--out', out/(track+'_math'))
        r = load(out/(track+'_math')/'receipt.json')
        assert r['status'] == 'COMPLETE' and r['pages'] == 1651 and r['extra_calls'] == 0
        if do_dot:
            dot(track, out/(track+'_math'))
            sizing(track, out/(track+'_dot')/'predictions', destination=track+'_before_labels')
            labels(track, out/(track+'_before_labels')/'predictions')

    def dot(track, source):
        step(track+'_dot', [PYTHON, '-B', 'scripts/replay_phase2_dot_leader_v1.py',
             '--source', source, '--out', out/(track+'_dot')])
        r = load(out/(track+'_dot')/'receipt.json')
        assert r['status'] == 'COMPLETE_DIAGNOSTIC_UNADOPTED' and r['pages'] == 1651
        assert r['new_model_calls'] == r['auxiliary_observations'] == 0 and r['GT_hidden']
        # The immutable producer predates D0150; adoption is recorded separately.
        save(out/(track+'_dot')/'adoption.json', dict(status='PRODUCTION_ACCEPTED', decision='D0150',
            producer_receipt_sha256=sha(out/(track+'_dot')/'receipt.json'), immutable_historical_status=r['status']))

    def sizing(track, predictions, destination=None):
        destination = destination or track
        step(track+'_sizing', [PYTHON, '-B', 'scripts/replay_phase2_math_delimiter_size_v1.py',
             '--predictions', predictions, '--out', out/destination])
        receipt = verify_sizing(out/destination, predictions)
        save(out/destination/'adoption.json', dict(status='PRODUCTION_ACCEPTED',
            acceptance_evidence=frozen['acceptance_evidence'],
            producer_receipt_sha256=sha(out/destination/'receipt.json'),
            immutable_historical_status=receipt['status']))

    def labels(track, predictions):
        destination = out/(track+'_before_short_leaders')
        step(track+'_labels', [PYTHON, '-B', 'scripts/replay_phase2_formula_label_v1.py',
             '--input', predictions, '--pages', pages, '--out', destination])
        receipt = verify_labels(destination, predictions, pages)
        save(destination/'adoption.json', dict(status='PRODUCTION_ACCEPTED',
            acceptance_evidence=frozen['acceptance_evidence'],
            producer_receipt_sha256=sha(destination/'receipt.json'),
            immutable_historical_status=receipt['status']))
        before_atoms = out/(track+'_before_atoms')
        step(track+'_short_leaders', [PYTHON, '-B', 'scripts/replay_phase2_dot_leader_v2.py',
             '--source', destination, '--pages', pages, '--out', before_atoms])
        receipt = verify_dot_leaders(before_atoms, destination, pages)
        save(before_atoms/'adoption.json', dict(status='PRODUCTION_ACCEPTED',
            acceptance_evidence=frozen['acceptance_evidence'],
            producer_receipt_sha256=sha(before_atoms/'receipt.json'),
            immutable_historical_status=receipt['status']))
        atom_source = before_atoms
        if track == 'B':
            # Panel observers own their GPU locks; never nest an outer lock.
            step('B_panel', prepare_panel(plan, frozen, before_atoms/'predictions'))
            state['B_panel_costs'] = verify_panel(out/'B_panel', before_atoms/'predictions',
                pages, plan=plan, frozen=frozen)
            atom_source = out/'B_panel/candidate'
        before_quantity = out/(track+'_before_quantity')
        step(track+'_atoms', [PYTHON, '-B', 'scripts/replay_phase2_table_atom_groups_v1.py',
             '--source', atom_source, '--out', before_quantity])
        receipt = verify_atoms(before_quantity, atom_source)
        save(before_quantity/'adoption.json', dict(status='PRODUCTION_ACCEPTED',
            acceptance_evidence=frozen['acceptance_evidence'],
            producer_receipt_sha256=sha(before_quantity/'receipt.json'),
            immutable_historical_status=receipt['status']))
        quantity_out = out/(track+'_before_mixed' if track == 'B' else track+'_before_render')
        step(track+'_quantity', [PYTHON, '-B', 'scripts/replay_phase2_quantity_units_v1.py',
             '--source', before_quantity/'predictions', '--out', quantity_out])
        receipt = verify_quantity(quantity_out, before_quantity/'predictions')
        save(quantity_out/'adoption.json', dict(status='PRODUCTION_ACCEPTED',
            acceptance_evidence=frozen['acceptance_evidence'],
            producer_receipt_sha256=sha(quantity_out/'receipt.json'),
            immutable_historical_status=receipt['status']))
        render_source = quantity_out
        if track == 'B':
            step('B_mixed', prepare_mixed(plan, frozen, quantity_out/'predictions'))
            step('B_mixed_compose', mixed_command(plan, frozen, quantity_out/'predictions', 'compose'))
            state['B_mixed_costs'] = verify_mixed(out/'B_mixed', quantity_out/'predictions', pages,
                plan['mixed_gpu'], frozen['mixed_budget'], plan=plan, frozen=frozen)
            render_source = out/'B_before_render'
            materialize_mixed(out/'B_mixed', render_source)
        rendered = out/(track+'_before_lists')
        step(track+'_render_groups', [RENDER_PYTHON, '-B', 'scripts/replay_phase2_render_groups_v4.py',
             '--source', render_source, '--out', rendered])
        verify_render_groups(rendered, render_source)
        listed = out/(track+'_before_inline')
        step(track+'_parallel_lists', [PYTHON, '-B', 'scripts/replay_phase2_parallel_lists_v1.py',
             '--source', rendered, '--pages', pages, '--out', listed])
        verify_parallel_lists(listed, rendered, pages)
        inline = out/(track+'_before_sparse')
        step(track+'_inline_display', [PYTHON, '-B', 'code/research/inline_cli_0034_v1.py',
             '--inputs', listed/'predictions', '--manifest', pages, '--out', inline/'predictions'])
        verify_inline_display(inline/'predictions', listed/'predictions', pages)
        footer_source = inline
        if track == 'B':
            step('B_sparse', prepare_sparse(plan, frozen, inline/'predictions'))
            step('B_sparse_compose', sparse_command(plan, 'compose'))
            sparse = inside(plan['sparse_output'])
            state['B_sparse_costs'] = verify_sparse(sparse, inline/'predictions', pages,
                                                   plan=plan, frozen=frozen)
            footer_source = out/'B_before_footer'
            materialize_sparse(sparse, footer_source)
        footer_out = out/(track+'_before_numeric' if track == 'B' else track+'_before_mode')
        step(track+'_table_math_footer', [PYTHON, '-B', FOOTER,
             '--input', footer_source/'predictions', '--pages', pages, '--out', footer_out])
        verify_footer(footer_out, footer_source/'predictions', pages)
        mode_source = footer_out
        if track == 'B':
            step('B_numeric_prepare', prepare_numeric(plan, frozen))
            # Its wrapper owns the deadline-bounded GPU lock; never nest it.
            step('B_numeric', approve_numeric(plan, frozen))
            numeric = inside(plan['numeric_output'])
            state['B_numeric_costs'] = verify_numeric(numeric, footer_out/'predictions',
                out/'native', pages, frozen=frozen, plan=plan)
            mode_source = out/'B_before_mode'
            materialize_numeric(numeric, mode_source)
        mode_out = out/(track+'_before_repeated')
        step(track+'_nested_mode', [PYTHON, '-B', MODE, '--input', mode_source/'predictions',
             '--pages', pages, '--out', mode_out])
        verify_mode(mode_out, mode_source/'predictions', pages)
        repeated_out = out/(track+'_before_header')
        step(track+'_repeated_text', [PYTHON, '-B', REPEATED, '--inputs', mode_out/'predictions',
             '--manifest', pages, '--out', repeated_out])
        verify_repeated(repeated_out, mode_out/'predictions', pages, frozen=frozen)
        header_out = out/(track+'_before_prose')
        step(track+'_header_group', [PYTHON, '-B', HEADER, '--inputs', repeated_out/'predictions',
             '--manifest', pages, '--out', header_out])
        verify_header(header_out, repeated_out/'predictions', pages, frozen=frozen)
        prose_out = out/(track+'_before_array_label')
        step(track+'_mixed_prose', [PYTHON, '-B', PROSE, '--inputs', header_out/'predictions',
             '--pages', pages, '--out', prose_out])
        verify_prose(prose_out, header_out/'predictions', pages, frozen=frozen)
        array_out = out/('B_before_brace' if track == 'B' else track+'_before_list_order')
        step(track+'_array_label', [PYTHON, '-B', ARRAY_LABEL, '--inputs', prose_out/'predictions',
             '--pages', pages, '--out', array_out])
        verify_array_label(array_out, prose_out/'predictions', pages, frozen=frozen)
        if track == 'B':
            step('B_brace', prepare_brace(plan, frozen))
            brace = inside(plan['brace_output'])
            costs, seconds = verify_brace(brace, array_out/'predictions', pages, plan=plan, frozen=frozen)
            state['B_brace_costs'] = costs
            state['B_brace_verification_seconds'] = seconds
            materialize_brace(brace, out/'B_before_shared_row')
            step('B_shared_row_prepare', prepare_shared_row(plan, frozen))
            step('B_shared_row_observe', approve_shared_row(plan, frozen))
            shared = inside(plan['shared_row_output'])
            step('B_shared_row_compose', [PYTHON, '-B', SHARED_ROW, 'compose', '--out', shared])
            costs, seconds = verify_shared_row(shared, out/'B_before_shared_row/predictions',
                out/'native', pages, plan=plan, frozen=frozen)
            state['B_shared_row_costs'] = costs
            state['B_shared_row_verification_seconds'] = seconds
            materialize_shared_row(shared, out/'B_before_column')
            step('B_column_prepare', prepare_column(plan, frozen))
            step('B_column_observe', approve_column(plan, frozen))
            column = inside(plan['column_output'])
            step('B_column_compose', [PYTHON, '-B', COLUMN, 'compose', '--out', column])
            costs, seconds = verify_column(column, out/'B_before_column/predictions', out/'native', pages, plan=plan, frozen=frozen)
            state['B_column_costs'] = costs
            state['B_column_verification_seconds'] = seconds
            materialize_tail(column/'selected_predictions', out/'B_before_list_order')
        list_source = out/(track+'_before_list_order')/'predictions'
        list_out = out/(track+'_list_order')
        step(track+'_list_order', [PYTHON, '-B', LIST_RUNNER, '--inputs', list_source, '--pages', pages, '--out', list_out])
        state[track+'_list_order_verification'] = verify_tail(list_source, list_out/'generator_predictions', pages, 'list')
        materialize_tail(list_out/'generator_predictions', out/(track+'_before_closed'))
        closed = out/(track+'_before_repeated_lines')
        step(track+'_closed_record', [PYTHON, '-B', 'scripts/replay_phase2_closed_record_v2.py', '--inputs', out/(track+'_before_closed')/'predictions', '--pages', pages, '--out', closed])
        state[track+'_closed_record_verification'] = verify_tail(out/(track+'_before_closed')/'predictions', closed/'predictions', pages, 'closed')
        repeated = out/(track+'_before_prose_recovery' if track == 'B' else track+'_before_semantic')
        step(track+'_repeated_lines', [PYTHON, '-B', REPEATED_LINES, '--inputs', closed/'predictions', '--pages', pages, '--out', repeated])
        state[track+'_repeated_lines_verification'] = verify_lines(repeated, closed/'predictions', pages)
        semantic_source = repeated/'predictions'
        if track == 'B':
            step('B_prose_recovery', prepare_prose_recovery(plan, frozen))
            prose_recovery = inside(plan['prose_output'])
            costs, seconds = verify_prose_recovery(prose_recovery, semantic_source, pages, plan=plan, frozen=frozen)
            state['B_prose_recovery_costs'] = costs
            state['B_prose_recovery_verification_seconds'] = seconds
            materialize_tail(prose_recovery/'selected_predictions', out/'B_before_semantic')
            semantic_source = out/'B_before_semantic/predictions'
        before_centered = out/(track+'_before_centered')
        step(track+'_semantic_tails', [PYTHON, '-B', 'scripts/replay_phase2_semantic_tails_v2.py', '--inputs', semantic_source, '--pages', pages, '--out', before_centered])
        state[track+'_semantic_tails_verification'] = verify_semantic_tails(semantic_source, before_centered, pages)
        step(track+'_centered_record', prepare_centered(plan, frozen, track))
        state[track+'_centered_record_verification'] = verify_centered(before_centered/'predictions', out/('B_before_skew' if track == 'B' else 'A_before_column_bridge'), pages, frozen=frozen, plan=plan, track=track)
        if track == 'B':
            step('B_skew_context', prepare_skew(plan, frozen))
            state['B_skew_costs'] = verify_skew(inside(plan['skew_output']), out/'B_before_skew/predictions', pages, plan=plan, frozen=frozen)
            step('B_empty_cell', prepare_empty(plan, frozen))
            state['B_empty_costs'], state['B_empty_verification_seconds'] = verify_empty(inside(plan['empty_output']), inside(plan['skew_output'])/'selected_predictions', pages, plan=plan, frozen=frozen)
        bridge_source = inside(plan['empty_output'])/'selected_predictions' if track == 'B' else out/'A_before_column_bridge/predictions'
        step(track+'_column_bridge', prepare_column_bridge(plan, frozen, track, bridge_source))
        state[track+'_column_bridge_verification'] = verify_column_bridge(inside(plan['column_bridge_'+track+'_output']), bridge_source, pages, plan=plan, frozen=frozen, track=track)
        materialize_tail(inside(plan['column_bridge_'+track+'_output'])/'selected_predictions', out/track)

    write()
    try:
        verify()
        if plan.get('native_input'):
            # Resume from an existing native output of the same weights and protocol (checked below).
            assert (out/'native/run.json').exists()
            state['steps'].append(dict(name='native', reused=plan['native_input']))
            write()
        else:
            step('native', [PYTHON, '-B', 'code/runtime/run_native.py', '--pages', pages,
                 '--out', out/'native', '--port', str(28021 + 100*int(plan['gpu'])), '--audit'], plan['gpu'])
        sys.path.insert(0, str(ROOT/'code/experimenter'))
        from single_model_native_runtime_v1 import verify_native
        from single_model_selective_v1 import dependencies
        binding = verify_native(out/'native', pages)
        save(out/'native_binding.json', binding)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = []
            argv = prepare_b(plan, frozen, dependencies())
            verify()
            state['background_core'] = dict(status='ADMITTED', input='this_repeat_native')
            write()
            def process_a():
                pure('A_base', 'code/research/run_native_rules_track_a_v1.py', '--native', out/'native',
                     '--pages', pages, '--out', out/'A_base', '--freeze', inside(frozen['rules_freeze']), '--verify-native')
                validate_rules(out/'A_base')
                math_dot('A', out/'A_base')
            def run_core():
                with gpu_lock(plan['b_gpu'], deadline):
                    from phase2_runtime_guard_v1 import guard
                    binding = guard(plan['b_gpu'])
                    assert binding['container_id'] == frozen['services'][plan['b_gpu']]['container_id']
                    save(out/'B_core_tail_service.json', binding)
                    return command('B_core_tail', argv)
            def commit_core(result, error):
                state['background_core'] = dict(status='FAILED' if error else 'COMPLETE', error=repr(error) if error else None)
                if result is not None: state['steps'].append(result)
                if (core/'actual_costs.json').exists(): state['B_core_costs'] = load(core/'actual_costs.json')
                write()
            run_with_background(process_a, run_core, commit_core, pool)
            verify()
            b = load(core/'pipeline.json')
            assert b['status'] == 'COMPLETE' and b['inference_complete'] and b['native_run'] == str(out/'native')
            validate_rules(Path(str(core)+'_tail'))
            state['B_core_costs'] = load(core/'actual_costs.json')
            assert state['B_core_costs']['extra_requests'] <= frozen['maximum_extra_requests']
            math_dot('B', Path(str(core)+'_tail'), do_dot=False)
            grid_argv = prepare_grid(plan, frozen)
            step('B_grid', grid_argv, plan['grid_gpu'])
            grid = inside(plan['grid_output'])
            g = load(grid/'execution.json')
            assert g['status'] == 'COMPLETE' and g['pages'] == 1651 and g['GT_hidden']
            state['B_grid_costs'] = load(grid/'actual_costs.json')
            dot('B', grid)
            step('B_fragment', prepare_fragment(plan, frozen))
            fragment_costs = verify_fragment(out/'B_fragment', out/'B_dot/predictions',
                out/'native/predictions', out/'native/audit/http.jsonl', pages,
                dict(frozen, _delivery=plan['delivery']))
            state['B_fragment_costs'] = fragment_costs
            sizing('B', out/'B_fragment/candidate', destination='B_before_resolution')
            # Runtime acquires its own deadline-aware GPU lock. Do not nest that lock.
            step('B_resolution', prepare_resolution(plan, frozen))
            resolution_costs = verify_resolution(out/'B_resolution',
                out/'B_before_resolution/predictions', out/'native', pages,
                dict(frozen, _delivery=plan['delivery']), gpu=plan['resolution_gpu'])
            state['B_resolution_costs'] = resolution_costs
            pure('B_resolution_math', 'code/research/phase2_replay_math_prime_v1.py',
                 '--predictions', out/'B_resolution/predictions', '--out', out/'B_resolution_math')
            dot('B_resolution', out/'B_resolution_math')
            sizing('B_resolution', out/'B_resolution_dot/predictions', destination='B_resolution_tail')
            step('B_retention', [PYTHON, '-B', 'scripts/apply_phase2_resolution_retention_v1.py',
                 '--baseline', out/'B_before_resolution/predictions',
                 '--candidate', out/'B_resolution_tail/predictions', '--pages', pages, '--out', out/'B_before_labels'])
            retention = verify_retention(out/'B_before_labels', out/'B_before_resolution/predictions',
                out/'B_resolution_tail/predictions', pages)
            save(out/'B_before_labels/adoption.json', dict(status='PRODUCTION_ACCEPTED',
                acceptance_evidence=frozen['acceptance_evidence'],
                producer_receipt_sha256=sha(out/'B_before_labels/receipt.json'),
                immutable_historical_status=retention['status']))
            labels('B', out/'B_before_labels/predictions')
            costs = state['B_core_costs']
            grid_costs = state['B_grid_costs']
            assert grid_costs['failed'] == grid_costs['missing_usage'] == 0
            state['B_costs'] = dict(extra_requests=costs['extra_requests']+grid_costs['actual_attempts']+fragment_costs['actual_attempts']+resolution_costs['actual_attempts']+state['B_panel_costs']['actual_attempts']+state['B_mixed_costs']['actual_attempts']+state['B_sparse_costs']['actual_attempts']+state['B_numeric_costs']['actual_attempts']+state['B_brace_costs']['actual_attempts']+state['B_shared_row_costs']['actual_attempts']+state['B_column_costs']['actual_attempts']+state['B_prose_recovery_costs']['actual_attempts']+state['B_skew_costs']['actual_attempts']+state['B_empty_costs']['actual_attempts'],
                extra_tokens={k:costs['extra_tokens'][k]+grid_costs['extra_'+k]+fragment_costs['extra_'+k]+resolution_costs['extra_'+k]+state['B_panel_costs']['extra_'+k]+state['B_mixed_costs']['extra_'+k]+state['B_sparse_costs']['extra_'+k]+state['B_numeric_costs']['extra_'+k]+state['B_brace_costs']['extra_'+k]+state['B_shared_row_costs']['extra_'+k]+state['B_column_costs']['extra_'+k]+state['B_prose_recovery_costs']['extra_'+k]+state['B_skew_costs']['extra_'+k]+state['B_empty_costs']['extra_'+k]
                              for k in ['prompt_tokens', 'completion_tokens']},
                core=state['B_core_costs'], grid=grid_costs, fragment=fragment_costs, resolution=resolution_costs, panel=state['B_panel_costs'], mixed=state['B_mixed_costs'], sparse=state['B_sparse_costs'], numeric=state['B_numeric_costs'], brace=state['B_brace_costs'], shared_row=state['B_shared_row_costs'], column=state['B_column_costs'], prose_recovery=state['B_prose_recovery_costs'], skew=state['B_skew_costs'],empty=state['B_empty_costs'], pure_rules_extra_requests=0)
            state.update(inference_complete=True)
            write()
        # Final zero-call tail on the final B predictions: table-cell writing conventions
        # (numeric-range dash, CJK-digit spacing, \(..\) -> $..$).
        pure('B_table_cell_style', 'code/research/table_cell_style_v3.py',
             '--src', out/'B/predictions', '--dst', out/'B_final/predictions', '--manifest', pages)
        style = load(out/'B_final/predictions/receipt.json')
        assert style['pages'] == 1651 and style['HTTP'] == style['model_calls'] == 0 and not style['gt_used']
        state['B_table_cell_style'] = {k: style[k] for k in ['changed_pages', 'stats', 'output_tree_sha256']}
        verify()
        for track in ['native', 'A', 'B', 'B_final']:
            source = out/track/'predictions' if track != 'native' else out/'native/predictions'
            assert len(list((source/'markdown').glob('*.md'))) == 1651, track
        state.update(status='COMPLETE')
    except BaseException as error:
        state.update(status='FAILED', error=repr(error))
        raise
    finally:
        write()


if __name__ == '__main__':
    main()
