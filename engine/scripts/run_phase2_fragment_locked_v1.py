"""Run the unchanged fragment-v3 entry under the shared GPU3 lock and hidden GT."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT/'code/research/phase2_fragment_runtime_v3.py'
GT = ['/opt/p2t10/hidden/OmniDocBench.json',
      '/opt/p2t10/hidden/source_validation_v2_references.jsonl',
      '/opt/p2t10/hidden/source_validation_v1_references.jsonl']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-argv', required=True)
    args = parser.parse_args()
    spec_path = Path(args.runtime_argv).resolve()
    assert spec_path.is_relative_to(ROOT)
    spec = json.loads(spec_path.read_text())
    assert spec['entry_sha256'] == hashlib.sha256(ENTRY.read_bytes()).hexdigest()
    assert isinstance(spec['argv'], list) and all(isinstance(v, str) for v in spec['argv'])
    output = Path(spec['argv'][spec['argv'].index('--out')+1]).resolve()
    assert output.is_relative_to(ROOT) and not output.exists()
    phase = json.loads((ROOT/'control/phase2_plan.json').read_text())
    end = dt.datetime.fromisoformat(phase['deadline_at' if '--permit' in spec['argv'] else 'drain_by']).timestamp()
    path = ROOT/'control/phase2_final_gpu_locks/3.lock'
    path.parent.mkdir(exist_ok=True)
    start = time.monotonic()
    with path.open('a+') as lock:
        while True:
            assert time.time() < end
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(1)
        hidden = [p for p in GT if Path(p).exists()]
        shell = 'set -euo pipefail\nn="$1"; shift\nfor ((i=0;i<n;i++)); do mount --bind /dev/null "$1"; test ! -s "$1"; shift; done\nexec "$@"'
        argv = ['unshare', '--mount', '--propagation', 'private', '/bin/bash', '-c', shell,
                'phase2-fragment', str(len(hidden)), *hidden,
                sys.executable, '-B', str(ENTRY), *spec['argv']]
        result = subprocess.run(argv, cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        record = dict(status='COMPLETE' if result.returncode == 0 else 'FAILED',
                      returncode=result.returncode, known_GT_paths_hidden=hidden,
                      GPU='3', lock=str(path), elapsed_seconds=time.monotonic()-start,
                      runtime_entry_sha256=spec['entry_sha256'],
                      wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      argv_spec_sha256=hashlib.sha256(spec_path.read_bytes()).hexdigest(),
                      inference_namespace_network='Local same-model API available; no network isolation claim')
        receipt = output.parent/(output.name+'.wrapper_receipt.json')
        receipt.write_text(json.dumps(record, indent=2)+'\n')
        result.check_returncode()


if __name__ == '__main__':
    main()
