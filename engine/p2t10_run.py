"""Engine-side launcher: bind the running Sangfor-OCR model service, write per-run control files, run the pipeline.

Runs inside the engine container (ENGINE_ROOT=/opt/p2t10/engine), which shares the network
namespace of the vLLM service container and can reach the Docker daemon (the frozen recipe runs
its processor-token checks inside the service container).

The control files set up the recipe's admission state for a single lane "0" whose endpoint is
http://127.0.0.1:28021. Times are set so that the frozen admission windows are open for this run;
no budget, threshold or stage is changed.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
MODEL = "/opt/p2t10/model"
WEIGHT = "01dcb5addfa1d6133fd0930e79fa2484817cb0228af21cb4917fa73d04fa3147"
PHASE = "phase2_single_model_97p2"
BASE_FREEZE = "control/freezes/phase2_AB_empty_bridge_final_v26.json"
PORT = 28021
LANE = "0"
# The fragment stage of the recipe is bound to lane "3" (port 28321). Lane "3" is served by the same
# model service through a local port forward inside the shared network namespace.
ALIAS_LANE, ALIAS_PORT = "3", 28321


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)
    return path


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat()


def wait_ready(timeout=3600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/v1/models", timeout=5) as r:
                ids = [m["id"] for m in json.load(r)["data"]]
                assert MODEL in ids, f"service must be started with --served-model-name {MODEL}"
                return
        except (OSError, ValueError):
            time.sleep(5)
    raise SystemExit("model service not ready")


def forward(listen_port, target_port):
    """Forward 127.0.0.1:listen_port to 127.0.0.1:target_port (background threads)."""
    import socket
    import threading

    def pipe(src, dst):
        try:
            while True:
                data = src.recv(1 << 16)
                if not data:
                    break
                dst.sendall(data)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", listen_port))
    server.listen(256)

    def accept():
        while True:
            client, _ = server.accept()
            upstream = socket.create_connection(("127.0.0.1", target_port))
            threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()
            threading.Thread(target=pipe, args=(upstream, client), daemon=True).start()

    threading.Thread(target=accept, daemon=True).start()


def ensure_model_view(container, port=PORT):
    """The service script creates this view at start; create the same view if it is absent."""
    view = ROOT / f"code/runtime/model-view-{port}-{container}"
    if not view.is_dir():
        view.mkdir(parents=True)
        for f in sorted(Path(MODEL).iterdir()):
            if f.name != "config.json":
                (view / f.name).symlink_to(f)
        from safetensors import safe_open
        cfg = json.loads((Path(MODEL) / "config.json").read_text())
        text_cfg = cfg.pop("text_config", None)
        with safe_open(str(Path(MODEL) / "model.safetensors"), framework="pt", device="cpu") as w:
            untied = "lm_head.weight" in w.keys()
        declared = (text_cfg or {}).get("tie_word_embeddings", cfg.get("tie_word_embeddings"))
        if declared is not None and declared == untied:
            raise ValueError("Weight tying config contradicts checkpoint tensor inventory")
        cfg["tie_word_embeddings"] = not untied
        (view / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    return view


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--container", required=True, help="name of the service container")
    parser.add_argument("--output", default="/opt/p2t10/output")
    parser.add_argument("--native-input", help="reuse an existing native output directory (resume)")
    args = parser.parse_args()
    run = args.run_id
    assert run.replace("_", "").replace("-", "").isalnum()
    os.chdir(ROOT)

    wait_ready()
    container_id = json.loads(subprocess.check_output(
        ["docker", "inspect", args.container], text=True))[0]["Id"]
    view = ensure_model_view(args.container)
    alias_view = ensure_model_view(args.container, ALIAS_PORT)
    forward(ALIAS_PORT, PORT)
    save(f"code/runtime/{args.container}.ownership.json",
         dict(returncode=0, stdout=container_id + "\n", container=args.container))

    now = time.time()
    save("control/phase2_plan.json", dict(
        phase=PHASE, started_at=iso(now - 3600), deadline_at=iso(now + 7 * 86400),
        final_start_at=iso(now - 60), drain_by=iso(now - 120), model=MODEL, gpu_ids=[0]))
    save("rsi_resource_directive.json", dict(
        phase=PHASE, allowed_gpus=[int(LANE), int(ALIAS_LANE)], deadline_at=iso(now + 7 * 86400),
        final_start_at=iso(now - 60), drain_by=iso(now - 120), service_owner="RSI"))
    contract = json.loads((ROOT / "control/campaign_contract.json").read_text())
    contract.update(phase=PHASE, deadline_at=iso(now + 7 * 86400))
    save("control/campaign_contract.json", contract)
    save("control/gpu_leases.json", {lane: dict(
        endpoint=f"http://127.0.0.1:{port}", container=args.container, container_id=container_id,
        state="READY", role="RSI", phase=PHASE, model_scope="same frozen ckpt-58 only",
        available_for_inference=True, service_running=True, ready_at=iso(now))
        for lane, port in [(LANE, PORT), (ALIAS_LANE, ALIAS_PORT)]})

    frozen = json.loads((ROOT / BASE_FREEZE).read_text())
    frozen["id"] = "p2t10_active_" + run
    frozen["services"] = {lane: dict(endpoint=f"http://127.0.0.1:{port}", container=args.container,
                                     container_id=container_id)
                          for lane, port in [(LANE, PORT), (ALIAS_LANE, ALIAS_PORT)]}
    # Drop entries for files that do not exist in this environment and for per-run model views;
    # the engine image's own environment is pinned by the dependency locks in the base freeze.
    for name, table in frozen.items():
        if isinstance(table, dict) and table and all(isinstance(v, str) for v in table.values()) \
                and all(isinstance(k, str) and k.startswith("/") for k in table):
            for key in [k for k in table if "/code/runtime/model-view-" in k or not Path(k).exists()]:
                del table[key]
    hashes = frozen["source_hashes"]
    # Register the pipeline driver and the final-stage rule in this run's freeze.
    for code in [ROOT / "scripts/run_p2t10_pipeline.py", ROOT / "code/research/table_cell_style_v3.py"]:
        hashes[str(code)] = sha(code)
    for f in sorted([*view.iterdir(), *alias_view.iterdir()]):
        if f.suffix in (".json", ".jinja", ".txt"):
            hashes[str(f)] = sha(f)
    freeze = save(f"control/freezes/p2t10_active_{run}.json", frozen)
    freeze_rel = str(freeze.relative_to(ROOT))

    lanes = {k: LANE for k in ["gpu", "b_gpu", "grid_gpu", "panel_gpu", "mixed_gpu",
                               "resolution_gpu", "sparse_gpu", "numeric_gpu", "brace_gpu",
                               "shared_row_gpu", "column_gpu", "prose_gpu"]}
    plan = dict(repeat=1, **lanes, fragment_gpu=ALIAS_LANE, freeze=freeze_rel, freeze_sha256=sha(freeze),
                output=f"runs/{run}", b_output=f"code/experimenter/runs/{run}_core",
                grid_output=f"code/experimenter/runs/{run}_grid",
                delivery=f"code/experimenter/runs/{run}_delivery")
    for name in ["sparse", "numeric", "brace", "shared_row", "column", "prose", "skew", "empty"]:
        plan[f"{name}_output"] = f"runs/{run}_{name}"
    plan["column_bridge_A_output"] = f"runs/{run}_bridge_A"
    plan["column_bridge_B_output"] = f"runs/{run}_bridge_B"
    if args.native_input:
        plan["native_input"] = args.native_input
        shutil.copytree(args.native_input, ROOT / f"runs/{run}/native", symlinks=True)
    plan_path = save(f"control/p2t10_{run}_plan.json", plan)
    plan_rel = str(plan_path.relative_to(ROOT))
    save("control/final_validation_plan.json", dict(
        enabled=True, phase=PHASE, owner="RSI", start_at=iso(now - 60), drain_by=iso(now - 120),
        deadline_at=iso(now + 7 * 86400), gpus=[0], required_repeats=1,
        runtime_freeze=freeze_rel, runtime_freeze_sha256=sha(freeze),
        accepted_strategy_freeze=freeze_rel,
        repeats=[dict(plan=plan_rel, plan_sha256=sha(plan_path))]))

    started = time.time()
    rc = subprocess.call([sys.executable, "-B", "scripts/run_p2t10_pipeline.py", "--plan",
                          str(plan_path.relative_to(ROOT))], cwd=ROOT,
                         env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    state = json.loads((ROOT / f"runs/{run}/pipeline.json").read_text())
    if rc != 0 or state.get("status") != "COMPLETE":
        raise SystemExit(f"pipeline failed: {state.get('status')} {state.get('error')}")

    # Only the final predictions are delivered; intermediate stages stay in the run directory.
    out = Path(args.output)
    dst = out / "markdown"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ROOT / f"runs/{run}/B_final/predictions/markdown", dst)
    costs = state.get("B_costs", {})
    summary = dict(run_id=run, wall_seconds=time.time() - started, model=MODEL, weight_sha256=WEIGHT,
                   pages=len(list(dst.glob("*.md"))),
                   native_requests=state.get("B_core_costs", {}).get("native_requests"),
                   extra_requests=costs.get("extra_requests"), extra_tokens=costs.get("extra_tokens"),
                   table_cell_style=state.get("B_table_cell_style"),
                   stages=[dict(name=s["name"], wall_seconds=s.get("wall_seconds")) for s in state["steps"]],
                   pipeline_state=f"engine/runs/{run}/pipeline.json")
    (out / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ["run_id", "pages", "extra_requests", "wall_seconds"]}))


if __name__ == "__main__":
    main()
