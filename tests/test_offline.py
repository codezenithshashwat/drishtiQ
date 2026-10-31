"""The app must work with no network: any outbound connection attempt fails this test (sockets blocked in Python)."""
import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GUARD = r"""
import socket, sys
_connect = socket.socket.connect
def guarded(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise OSError(f"network blocked by test: {address}")
    return _connect(self, address)
socket.socket.connect = guarded
sys.path.insert(0, sys.argv[1] + "/src")
sys.path.insert(0, sys.argv[1])
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
import backend.app  # noqa: F401  (same import path as the server)
from inference import Pipeline
result = Pipeline().analyze(open(sys.argv[2], "rb").read())
assert result["status"] in ("ok", "rejected"), result.get("status")
print("OFFLINE-OK", result.get("grading", {}).get("grade"))
"""


def test_analysis_runs_with_network_blocked():
    with open(ROOT / "data/interim/manifests/idrid_grading_train_clean.csv", newline="") as f:
        path = ROOT / next(csv.DictReader(f))["filepath"]
    out = subprocess.run([sys.executable, "-c", GUARD, str(ROOT), str(path)], capture_output=True, text=True, timeout=600, cwd=ROOT)
    assert "OFFLINE-OK" in out.stdout, out.stderr[-2000:]
