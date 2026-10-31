"""Worklist scale check (ADR-033): a throwaway store with 500 cases cloned from real stored analyses.

    .venv\Scripts\python tools\worklist_scale.py build --n 500            # -> results/cache/worklist_scale_store
    .venv\Scripts\python tools\worklist_scale.py record --render-ms X --api-ms Y   # -> results/worklist_scale.json

Cloning avoids running the pipeline 500 times: the worklist only reads stored analyses. Render time is measured in a
browser against a backend started with RS_DATA_DIR pointing at the throwaway store. Measurement only.
"""
import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "results/cache/worklist_scale_store"


def build(n):
    src = sqlite3.connect(ROOT / "data/app/cases.sqlite")
    src.row_factory = sqlite3.Row
    rows = src.execute("SELECT * FROM cases").fetchall()
    if not rows:
        raise SystemExit("the local store has no cases to clone; seed it first (tools/seed_demo_cases.py)")
    if STORE.exists():
        shutil.rmtree(STORE)
    (STORE / "images").mkdir(parents=True)
    sys.path.insert(0, str(ROOT))
    from backend import store
    store.DIR, store.IMAGES = STORE, STORE / "images"
    db = store.connect()
    for i in range(n):
        r = rows[i % len(rows)]
        src_img = ROOT / "data/app/images" / f"{r['id']}.{r['image_ext']}"
        cid = f"RS-{1001 + i}"
        shutil.copyfile(src_img, STORE / "images" / f"{cid}.{r['image_ext']}")
        db.execute("INSERT INTO cases VALUES (?,?,?,?,?,?,?,?, 'new')",
                   (cid, r["created"], f"SCALE-{i + 1:03d}", r["eye"], r["source"], r["image_ext"], r["analysis"], r["analysed_with"]))
    db.commit()
    print(f"RESULT: {n} cases in {STORE.relative_to(ROOT)} (cloned from {len(rows)} stored analyses)")


def record(render_ms, api_ms, n):
    out = dict(cases=n, render_ms=render_ms, api_ms=api_ms, method="browser: navigation start to all table rows rendered; api: GET /api/cases",
               note="measurement only; nothing tuned")
    (ROOT / "results/worklist_scale.json").write_text(json.dumps(out, indent=2))
    print(f"RESULT: {n} cases: API {api_ms:.0f} ms, render {render_ms:.0f} ms")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--n", type=int, default=500)
    r = sub.add_parser("record")
    r.add_argument("--render-ms", type=float, required=True)
    r.add_argument("--api-ms", type=float, required=True)
    r.add_argument("--n", type=int, default=500)
    a = ap.parse_args()
    build(a.n) if a.cmd == "build" else record(a.render_ms, a.api_ms, a.n)
