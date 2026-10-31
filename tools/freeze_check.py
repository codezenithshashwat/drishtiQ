"""Freeze detector (ADR-038): gaps of more than 15 minutes between GPU-monitor readings in queue/logs/gpu.csv.

    .venv\Scripts\python tools\freeze_check.py      # writes results/freezes.json

The queue logs a reading every 10 minutes while it runs, so a longer gap means the machine was suspended (lid, sleep,
power) or the queue was stopped. Windows' own reason, when known, is in the System event log (Kernel-Power 506/507).
"""
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAP_MIN = 15


def main():
    rows = list(csv.DictReader(open(ROOT / "queue/logs/gpu.csv", encoding="utf-8")))
    times = [dt.datetime.fromisoformat(r["time"]) for r in rows]
    gaps = [dict(start=a.isoformat(timespec="minutes"), end=b.isoformat(timespec="minutes"), minutes=round((b - a).total_seconds() / 60))
            for a, b in zip(times, times[1:]) if (b - a).total_seconds() > GAP_MIN * 60]
    out = dict(threshold_minutes=GAP_MIN, readings=len(rows), freezes=gaps, total_frozen_minutes=sum(g["minutes"] for g in gaps))
    (ROOT / "results/freezes.json").write_text(json.dumps(out, indent=2))
    print(f"RESULT: {len(gaps)} freeze(s) over {GAP_MIN} min, {out['total_frozen_minutes']} min in total" + "".join(f"; {g['start']} -> {g['end']}" for g in gaps))


if __name__ == "__main__":
    main()
