"""rc-1 readiness check (ADR-038): is everything in place to tag the release candidate? Changes nothing; never tags.

    .venv\\Scripts\\python tools\\rc1_check.py      # writes results/rc1_readiness.json

Checks: every queue job finished (done / failed / skipped, none pending), preflight passes, the reported numbers
reproduce, the test suite passes, and the expected decision files exist. Tagging rc-1 stays a separate, deliberate step.
"""
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ["a2_swap", "a3_swap", "a2_ensemble", "s1_thresholds", "a3ens_swap", "a3ma_swap", "s2_stage01", "s3_stage34", "s4_corn",
            "eyepacs", "seg_trigger_loss", "seg_trigger_encoder", "a4_fusion", "pseudo_label", "tta_final"]


def ok(cmd):
    return subprocess.run([sys.executable, *cmd], cwd=ROOT, capture_output=True, text=True).returncode == 0


def main():
    jobs = yaml.safe_load((ROOT / "queue/jobs.yaml").read_text(encoding="utf-8"))["jobs"]
    state = json.loads((ROOT / "queue/state.json").read_text()) if (ROOT / "queue/state.json").exists() else {}
    # Jobs cancelled by owner decision (enabled: false or status "cancelled", ADR-041) count as finished and are listed.
    cancelled = [j["id"] for j in jobs if j["id"] != "rc1_check" and (not j.get("enabled", True) or state.get(j["id"], {}).get("status") == "cancelled")
                 and state.get(j["id"], {}).get("status") not in ("done", "failed", "skipped")]
    unfinished = [j["id"] for j in jobs if j["id"] != "rc1_check" and j["id"] not in cancelled
                  and state.get(j["id"], {}).get("status") not in ("done", "failed", "skipped")]
    failed = [j["id"] for j in jobs if state.get(j["id"], {}).get("status") == "failed"]
    missing = [d for d in EXPECTED if not (ROOT / f"queue/decisions/{d}.json").exists()]
    checks = dict(queue_unfinished=unfinished, queue_cancelled_by_owner=cancelled, queue_failed=failed, decisions_missing=missing,
                  preflight=ok(["preflight.py"]), reproduce=ok(["tools/reproduce.py", "--check"]), tests=ok(["-m", "pytest", "-q", "backend", "tests"]))
    ready = not unfinished and checks["preflight"] and checks["reproduce"] and checks["tests"]
    (ROOT / "results/rc1_readiness.json").write_text(json.dumps(dict(ready=ready, **checks), indent=2))
    print(f"RESULT: rc-1 {'READY' if ready else 'NOT ready'}: unfinished {unfinished or 'none'}; failed {failed or 'none'}; "
          f"missing decisions {missing or 'none'}; preflight {checks['preflight']}, reproduce {checks['reproduce']}, tests {checks['tests']}", flush=True)


if __name__ == "__main__":
    main()
