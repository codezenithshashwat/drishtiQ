"""Dummy queue job: ~60 s of 'epochs' with a resumable checkpoint; optionally fails once mid-run to test retry/resume."""
import json, sys, time
from pathlib import Path
ckpt = Path(sys.argv[1]); fail_once = "--fail-once" in sys.argv
state = json.loads(ckpt.read_text()) if ckpt.exists() else {"epoch": 0, "failed": False}
if state["epoch"]: print(f"resumed at epoch {state['epoch']}", flush=True)
for e in range(state["epoch"], 6):
    time.sleep(10); state["epoch"] = e + 1; ckpt.write_text(json.dumps(state)); print(f"epoch {e+1}/6", flush=True)
    if fail_once and e == 2 and not state["failed"]:
        state["failed"] = True; ckpt.write_text(json.dumps(state)); raise SystemExit("simulated crash")
print("RESULT: dummy finished 6 epochs", flush=True)
