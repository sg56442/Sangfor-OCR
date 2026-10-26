#!/usr/bin/env python3
"""Detach finite experiment jobs from a Codex tool/turn, with durable ownership.

Input is a JSON object with id, argv (no shell), and an optional log path.
The supervising process, child and output files are campaign-owned. No foreign
process is signalled. The campaign deadline bounds all launched work.
"""
import argparse
import datetime
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def ticks(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()[19]
    except OSError:
        return None


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def inside(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Output/spec outside campaign: {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--supervise", action="store_true")
    args = parser.parse_args()
    spec_path = inside(args.spec)
    spec = json.loads(spec_path.read_text())
    name = spec["id"]
    assert re.fullmatch(r"[a-zA-Z0-9_.-]+", name), name
    assert isinstance(spec["argv"], list) and spec["argv"] and all(isinstance(x, str) for x in spec["argv"])
    state_dir = ROOT / "control/owned_jobs"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / f"{name}.json"
    log = inside(spec.get("log", f"control/owned_jobs/{name}.log"))
    log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    # Inference/scoring children do not require the LLM provider credential.
    for key in ["FT1021_CODEX_KEY", "OPENAI_API_KEY", "CODEX_API_KEY"]:
        env.pop(key, None)
    if not args.supervise:
        lock = (state_dir / f"{name}.launch.lock").open("a+")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if state_path.exists():
            old = json.loads(state_path.read_text())
            if old.get("supervisor_pid") and ticks(old["supervisor_pid"]) == old.get("supervisor_start_ticks"):
                print(json.dumps({"status": "ALREADY_RUNNING", "state": str(state_path)}))
                return
            raise RuntimeError("This job id has a prior receipt; use a new id for an explicitly reviewed attempt")
        with log.open("a") as stream:
            proc = subprocess.Popen(
                [sys.executable, "-u", str(Path(__file__).resolve()), "--supervise", "--spec", str(spec_path)],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                start_new_session=True, close_fds=True, env=env,
            )
        receipt = {"at": now(), "supervisor_pid": proc.pid, "supervisor_start_ticks": ticks(proc.pid), "spec": str(spec_path)}
        write(state_dir / f"{name}.launch.json", receipt)
        print(json.dumps(receipt))
        return
    lock = (state_dir / f"{name}.run.lock").open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append("SIGNALLED"))
    signal.signal(signal.SIGINT, lambda *_: stop.append("SIGNALLED"))
    deadline = datetime.datetime.fromisoformat(json.loads((ROOT / "control/campaign_contract.json").read_text())["deadline_at"]).timestamp()
    state = {"id": name, "status": "STARTING", "started_at": now(), "supervisor_pid": os.getpid(), "supervisor_start_ticks": ticks(os.getpid()), "argv": spec["argv"], "spec": str(spec_path), "log": str(log)}
    write(state_path, state)
    proc = subprocess.Popen(spec["argv"], cwd=ROOT, stdin=subprocess.DEVNULL, start_new_session=True, env=env)
    child_ticks = ticks(proc.pid)
    state.update(status="RUNNING", child_pid=proc.pid, child_start_ticks=child_ticks)
    write(state_path, state)
    while proc.poll() is None:
        if stop or time.time() >= deadline:
            state["stop_reason"] = stop[0] if stop else "CAMPAIGN_DEADLINE"
            if ticks(proc.pid) == child_ticks:
                os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                if ticks(proc.pid) == child_ticks:
                    os.killpg(proc.pid, signal.SIGKILL)
            break
        state["heartbeat_at"] = now()
        write(state_path, state)
        time.sleep(5)
    code = proc.wait()
    state.update(status="COMPLETE" if code == 0 else "FAILED", returncode=code, ended_at=now())
    write(state_path, state)


if __name__ == "__main__":
    main()
