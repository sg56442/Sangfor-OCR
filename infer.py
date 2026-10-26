#!/usr/bin/env python3
"""Sangfor-OCR document parsing for OmniDocBench v1.6 (inference only).

Runs the frozen recipe: MinerU native two-step parsing with the Sangfor-OCR weights, deterministic
post-processing and bounded same-model re-reads. Writes one Markdown file per page image, named after the image, ready
for the official OmniDocBench end2end evaluation.

Requirements on the host: Python >= 3.8, Docker with the NVIDIA runtime, one GPU (80 GB class
recommended), the Sangfor-OCR weights, and the 1651 OmniDocBench v1.6 page images.

Example:
  python3 infer.py --images /path/OmniDocBench/images --model /path/Sangfor-OCR --out ./predictions --gpu 0
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

REPO = Path(__file__).resolve().parent
ENGINE = REPO / "engine"
PAGES = ENGINE / "code/runtime/runs/native_full1651_gpu5_v2/pages.json"
IMAGE_HASHES = REPO / "configs/omnidocbench_v1.6_images.sha256.json"
ENGINE_IMAGE = "sangfor-ocr-engine:1.0"
VLLM_IMAGE = "vllm/vllm-openai:v0.8.5"


def run(cmd, **kw):
    print("+", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(list(map(str, cmd)), check=True, **kw)


def docker_rm(name):
    subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def check_images(images, verify):
    pages = json.loads(PAGES.read_text())
    expected = {Path(p["image"]).name for p in pages}
    present = {p.name for p in images.iterdir() if p.is_file()}
    missing = sorted(expected - present)
    if missing:
        raise SystemExit(f"{len(missing)} of {len(expected)} OmniDocBench v1.6 images missing, e.g. {missing[:3]}")
    if verify:
        hashes = json.loads(IMAGE_HASHES.read_text())
        bad = [name for name, digest in sorted(hashes.items())
               if hashlib.sha256((images / name).read_bytes()).hexdigest() != digest]
        if bad:
            raise SystemExit(f"{len(bad)} images differ from the OmniDocBench v1.6 release, e.g. {bad[:3]}")
    return len(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images", required=True, type=Path, help="OmniDocBench v1.6 images directory")
    parser.add_argument("--model", required=True, type=Path, help="Sangfor-OCR checkpoint directory")
    parser.add_argument("--out", required=True, type=Path, help="output directory (Markdown per page)")
    parser.add_argument("--gpu", default="0", help="physical GPU index for the model service")
    parser.add_argument("--gpu-memory-utilization", default="0.7")
    parser.add_argument("--gpu-access", choices=["toolkit", "device"], default="toolkit",
                        help="toolkit: docker --gpus (NVIDIA Container Toolkit); device: pass /dev/nvidia* "
                             "through directly, for hosts where the toolkit cannot be used")
    parser.add_argument("--engine-image", default=ENGINE_IMAGE)
    parser.add_argument("--vllm-image", default=VLLM_IMAGE)
    parser.add_argument("--verify-images", action="store_true",
                        help="check every image against the OmniDocBench v1.6 release hashes")
    parser.add_argument("--keep-service", action="store_true", help="leave the model service running")
    parser.add_argument("--workdir", type=Path, default=REPO / "work",
                        help="per-run working copies of the engine (about 5 GB per run)")
    parser.add_argument("--resume-native", type=Path,
                        help="native output directory of an earlier run of this repository to resume from")
    parser.add_argument("--docker-arg", action="append", default=[],
                        help="extra argument for the model service container (repeatable), "
                             "e.g. a host-specific driver library mount")
    args = parser.parse_args()

    images, model, out = args.images.resolve(), args.model.resolve(), args.out.resolve()
    assert (model / "model.safetensors").is_file(), "model directory must contain model.safetensors"
    n = check_images(images, args.verify_images)
    out.mkdir(parents=True, exist_ok=True)

    # Every run starts from a pristine copy of the engine: no outputs of other runs exist in it.
    run_id = "p2t10_" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
    engine = (args.workdir / run_id / "engine").resolve()
    shutil.copytree(ENGINE, engine, symlinks=True)
    service = f"p2t10-vllm-{run_id.replace('_', '-')}"
    docker_rm(service)
    mounts = ["-v", f"{engine}:/opt/p2t10/engine", "-v", f"{model}:/opt/p2t10/model:ro"]
    try:
        if args.gpu_access == "toolkit":
            gpu_args = ["--gpus", f"device={args.gpu}"]
        else:
            gpu_args = ["--runtime=runc", "-e", "NVIDIA_VISIBLE_DEVICES=void"]
            for dev in [f"/dev/nvidia{args.gpu}", "/dev/nvidiactl", "/dev/nvidia-uvm", "/dev/nvidia-uvm-tools"]:
                gpu_args += ["--device", dev]
        run(["docker", "run", "-d", "--name", service, *gpu_args, "--shm-size", "16g",
             *mounts, "-v", f"{engine}/code/runtime/mineru_server.sh:/mineru_server.sh:ro", *args.docker_arg,
             "-e", "MODEL=/opt/p2t10/model", "-e", "PORT=28021", "-e", f"FT1021_VIEW_ID={service}",
             "-e", f"GPU_MEMORY_UTIL={args.gpu_memory_utilization}",
             "-e", "OMP_NUM_THREADS=4", "-e", "MKL_NUM_THREADS=4", "-e", "OPENBLAS_NUM_THREADS=1",
             "--entrypoint", "/bin/bash", args.vllm_image, "/mineru_server.sh"])
        started = time.time()
        # CAP_SYS_ADMIN: the zero-call stages run in their own network namespace (no network access).
        run(["docker", "run", "--rm", "--network", f"container:{service}", "--cap-add", "SYS_ADMIN",
             "-v", "/var/run/docker.sock:/var/run/docker.sock", *mounts,
             "-v", f"{images}:/opt/p2t10/images:ro", "-v", f"{out}:/opt/p2t10/output",
             *(["-v", f"{args.resume_native.resolve()}:/opt/p2t10/resume_native:ro"] if args.resume_native else []),
             args.engine_image, "python", "-B", "/opt/p2t10/engine/p2t10_run.py",
             "--run-id", run_id, "--container", service,
             *(["--native-input", "/opt/p2t10/resume_native"] if args.resume_native else [])])
        summary = json.loads((out / "run_summary.json").read_text())
        print(json.dumps(dict(pages=n, predictions=str(out / "markdown"), run_id=run_id, workdir=str(engine.parent),
                              extra_requests=summary.get("extra_requests"),
                              wall_minutes=round((time.time() - started) / 60, 1)), indent=2))
    finally:
        if not args.keep_service:
            docker_rm(service)


if __name__ == "__main__":
    sys.exit(main())
