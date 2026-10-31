"""Keep Windows from sleeping while the GPU queue runs (no power settings are changed).

Calls SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED), the per-process request media players use; Windows
drops it when this process exits. Exits by itself once the queue process (queue/queue.pid) is gone or queue/STOP exists.
Started detached by tools/start_keep_awake.ps1. The display may still turn off; only system sleep is blocked.
"""
import ctypes
import datetime as dt
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
Q = ROOT / "queue"
ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def queue_alive():
    pid_file = Q / "queue.pid"
    if not pid_file.exists() or (Q / "STOP").exists():
        return False
    pid = pid_file.read_text().strip()
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, creationflags=0x08000000).stdout
    return pid in out


def main():
    log = Q / "logs/keep_awake.log"
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now():%Y-%m-%dT%H:%M:%S} keep-awake started\n")
    while queue_alive():
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        time.sleep(60)
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now():%Y-%m-%dT%H:%M:%S} queue gone; keep-awake exiting\n")


if __name__ == "__main__":
    main()
