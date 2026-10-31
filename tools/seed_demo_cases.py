"""Fill the local case store with demo cases the models never trained on: IDRiD-val and APTOS-val images.

    .venv\\Scripts\\python tools\\seed_demo_cases.py [--archive-existing]

Selection is fixed by seed 17, never by looking at results: for each ICDR stage 0-4, one image from IDRiD-val and one
from APTOS-val; plus two images drawn at random from the validation images the quality gate flags. These images are
used for validation metrics only; nothing is tuned on displayed cases. Each image is its own single-eye case (no
patient linkage exists, so none is invented). Source "validation:<split>:<id>"; the UI labels them "Validation image,
not used for training". --archive-existing moves the current store to data/app/archive_<time>/ first (nothing deleted).
"""
import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from backend import store  # noqa: E402
from backend.app import signature  # noqa: E402
from eval import data  # noqa: E402
from inference import Pipeline  # noqa: E402

SPLITS = {"idrid_grading_val": "IDRiD", "aptos_val": "APTOS"}


def choose():
    rng = np.random.default_rng(17)
    picks, flagged = [], []
    for split in SPLITS:
        rows, _ = data.load_split(split)
        for g in range(5):
            cands = [r for r in rows if int(r["DR_grade"]) == g]
            picks.append((split, cands[int(rng.integers(len(cands)))]))
        for r in rows:
            if not Pipeline.quality(data.load_image(r["filepath"]))["usable"]:
                flagged.append((split, r))
    chosen = {(s, r["filepath"]) for s, r in picks}
    flagged = [f for f in flagged if (f[0], f[1]["filepath"]) not in chosen]
    for i in rng.choice(len(flagged), min(2, len(flagged)), replace=False):
        picks.append(flagged[int(i)])
    return picks, len(flagged)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-existing", action="store_true")
    args = ap.parse_args()
    if args.archive_existing and (store.DIR / "cases.sqlite").exists():
        dest = store.DIR / f"archive_{datetime.now():%Y%m%d_%H%M%S}"
        dest.mkdir(parents=True)
        shutil.move(str(store.DIR / "cases.sqlite"), dest / "cases.sqlite")
        if store.IMAGES.exists():
            shutil.move(str(store.IMAGES), dest / "images")
        print(f"archived previous store to {dest.relative_to(ROOT)}")
    picks, n_flagged = choose()
    db = store.connect()
    have = {r["source"] for r in store.cases(db)}
    pipe = Pipeline()
    sig = signature(pipe)
    for split, r in picks:
        image_id = r.get("image_id") or r.get("id_code")
        source = f"validation:{split}:{image_id}"
        if source in have:
            continue
        raw = (ROOT / r["filepath"]).read_bytes()
        result = pipe.analyze(raw)
        ext = Path(r["filepath"]).suffix.lstrip(".").lower()
        cid = store.add_case(db, f"{SPLITS[split]}-{image_id}", "unknown", source, raw, ext, result, sig)
        print(f"{cid} {split} {image_id}: specialist grade {r['DR_grade']}, AI stage {result.get('grading', {}).get('grade')}, "
              f"usable {result['quality']['usable']}", flush=True)
    print(json.dumps(dict(cases=len(store.cases(db)), quality_flagged_pool=n_flagged)))


if __name__ == "__main__":
    main()
