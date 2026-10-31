"""Conditional EyePACS 2015 (ADR-037). One queue job; each stage is resumable and recorded.

    .venv\\Scripts\\python tools\\eyepacs.py

1. Trigger: the app system's latest APTOS-val run has stage-1 recall < 0.55 or stage-4 recall < 0.70. Otherwise the
   decision "not triggered" is recorded and nothing is downloaded.
2. Disk: the archives (~35 GB) + extraction (~35 GB) must leave >= 40 GB free.
3. Download train images + trainLabels with the Kaggle CLI (competition diabetic-retinopathy-detection). The CLI reads
   its own API token; this script never reads, prints or stores it.
4. Extract (CRC-32 verified by zipfile), audit (structure-hash leak check vs IDRiD-val, APTOS-val, IDRiD clean test,
   DeepDRiD, Messidor-2 if present, distance <= 42; exact duplicates; grade counts), write configs/splits/eyepacs_train.csv.
5. Retrain the base grader with EyePACS as a 4th training dataset (same recipe, seed 17) and apply ADR-013 through
   tools/system_eval.py against the app system. EyePACS labels are single-grader (noisy); recorded.
"""
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from data.fingerprint import fingerprint, hamming_matrix, to_bits  # noqa: E402
from inference.system import system_name  # noqa: E402

COMP = "diabetic-retinopathy-detection"
ARCHIVE = ROOT / "data/raw/EyePACS/archive"
IMAGES = ROOT / "data/raw/EyePACS/train"
SPLIT = ROOT / "configs/splits/eyepacs_train.csv"
DECISION = ROOT / "queue/decisions/eyepacs.json"
AUDIT = ROOT / "results/audit"


def record(**kw):
    prev = json.loads(DECISION.read_text()) if DECISION.exists() else {}
    DECISION.write_text(json.dumps({**prev, **kw, "adr": "ADR-037"}, indent=2))


def trigger():
    app = json.loads((ROOT / "configs/app/app.json").read_text())
    name = system_name(app)
    rows = [r for r in csv.DictReader(open(ROOT / "results/registry.csv", encoding="utf-8"))
            if r["task"] == "grade" and r["model"] == name and r["eval_split"] == "aptos_val"]
    if not rows:
        raise SystemExit(f"no APTOS-val run for the app system {name}")
    g1, g4 = float(rows[-1]["recall_g1"]), float(rows[-1]["recall_g4"])
    return dict(system=name, run=rows[-1]["run_id"], recall_g1=g1, recall_g4=g4, triggered=bool(g1 < 0.55 or g4 < 0.70))


def kaggle(*args):
    exe = Path(sys.executable).with_name("kaggle.exe")
    subprocess.run([str(exe if exe.exists() else "kaggle"), *args], cwd=ROOT, check=True)


def download():
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    listing = subprocess.run([str(Path(sys.executable).with_name("kaggle.exe")), "competitions", "files", COMP, "--csv", "--page-size", "200"],
                             capture_output=True, text=True, check=True).stdout.splitlines()
    names = [l.split(",")[0] for l in listing[1:] if l.startswith(("train.zip", "trainLabels"))]
    for n in names:
        if not (ARCHIVE / n).exists():
            kaggle("competitions", "download", COMP, "-f", n, "-p", str(ARCHIVE))
    return names


def extract():
    labels_zip = next(ARCHIVE.glob("trainLabels*"))
    if labels_zip.suffix == ".zip":
        with zipfile.ZipFile(labels_zip) as z:
            z.extractall(ARCHIVE)
    parts = sorted(ARCHIVE.glob("train.zip.0*")) or sorted(ARCHIVE.glob("train.zip"))
    from data.extract_mmrdr import MultiPart
    IMAGES.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BufferedReader(MultiPart(parts), buffer_size=8 << 20)) as z:
        for info in z.infolist():
            if info.is_dir() or not info.filename.lower().endswith((".jpeg", ".jpg")):
                continue
            target = IMAGES / Path(info.filename).name
            if target.exists() and target.stat().st_size == info.file_size:
                continue
            with z.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)  # zipfile raises BadZipFile on a CRC-32 mismatch


def audit():
    labels = {r["image"]: int(r["level"]) for r in csv.DictReader(open(next(ARCHIVE.glob("trainLabels*.csv")), encoding="utf-8"))}
    files = sorted(IMAGES.glob("*.jpeg"))
    cache_p = AUDIT / "eyepacs/eyepacs_fingerprints.csv"
    cache_p.parent.mkdir(parents=True, exist_ok=True)
    cache = {r["path"]: r for r in csv.DictReader(open(cache_p, encoding="utf-8"))} if cache_p.exists() else {}
    for k, f in enumerate(files):
        rel = f.relative_to(ROOT).as_posix()
        if rel not in cache:
            fp = fingerprint(f)
            cache[rel] = dict(path=rel, sha256=fp["sha256"], shash=fp["shash"])
        if (k + 1) % 2000 == 0:
            print(f"hashed {k + 1}/{len(files)}", flush=True)
            with open(cache_p, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=["path", "sha256", "shash"])
                w.writeheader()
                w.writerows(cache.values())
    with open(cache_p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["path", "sha256", "shash"])
        w.writeheader()
        w.writerows(cache.values())
    rows = [cache[f.relative_to(ROOT).as_posix()] for f in files]
    h = to_bits([r["shash"] for r in rows])
    refs = {"IDRiD (val + clean test)": [r["shash"] for r in csv.DictReader(open(AUDIT / "aptos/idrid_all_fingerprints.csv", encoding="utf-8"))],
            "APTOS (train + val)": [r["shash"] for r in csv.DictReader(open(AUDIT / "aptos/aptos_fingerprints.csv", encoding="utf-8"))],
            "DeepDRiD": [r["shash"] for r in csv.DictReader(open(AUDIT / "deepdrid/deepdrid_fingerprints.csv", encoding="utf-8"))]}
    m2 = AUDIT / "messidor2/messidor2_fingerprints.csv"
    if m2.exists():
        refs["Messidor-2"] = [r["shash"] for r in csv.DictReader(open(m2, encoding="utf-8"))]
    leak, drop = {}, set()
    for name, ref in refs.items():
        hit = np.nonzero(hamming_matrix(h, to_bits(ref)).min(1) <= 42)[0]
        leak[name] = dict(reference_images=len(ref), matches=int(len(hit)))
        drop |= {rows[i]["path"] for i in hit}
    seen, dup = set(), 0
    out = []
    for f, r in zip(files, rows):
        if r["path"] in drop or f.stem not in labels:
            continue
        if r["sha256"] in seen:
            dup += 1
            continue
        seen.add(r["sha256"])
        out.append(dict(id_code=f.stem, filepath=r["path"], DR_grade=labels[f.stem], content_hash=r["sha256"]))
    with open(SPLIT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id_code", "filepath", "DR_grade", "content_hash"])
        w.writeheader()
        w.writerows(out)
    grades = {str(g): sum(1 for o in out if o["DR_grade"] == g) for g in range(5)}
    summary = dict(images=len(files), labelled=len(labels), leak_check=leak, removed_for_leak=len(drop), exact_duplicates_removed=dup,
                   training_images=len(out), grade_counts=grades, label_note="single grader per image (noisy labels)")
    (AUDIT / "eyepacs/audit_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main():
    t = trigger()
    record(trigger=t)
    if not t["triggered"]:
        print(f"RESULT: ADR-037 EyePACS not triggered (APTOS-val stage-1 recall {t['recall_g1']:.2f} >= 0.55 and stage-4 recall {t['recall_g4']:.2f} >= 0.70)")
        return
    free = shutil.disk_usage(ROOT).free / 2**30
    have = sum(p.stat().st_size for p in ARCHIVE.glob("*")) / 2**30 if ARCHIVE.exists() else 0
    if free - (70 - have) < 40:
        record(stopped=f"disk: {free:.0f} GB free, need about {70 - have:.0f} GB plus 40 GB headroom")
        raise SystemExit("not enough disk space for EyePACS; recorded")
    record(download=download())
    extract()
    summary = audit()
    record(audit=summary)
    app = json.loads((ROOT / "configs/app/app.json").read_text())
    base = app["grader"].removeprefix("finetune:")
    head = "reg" if "_reg_" in base else "ce"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    subprocess.run([sys.executable, "src/train/finetune_mixed.py", "--head", head, "--size", "384", "--seed", "17", "--version", "v1ep",
                    "--extra-split", "eyepacs_train"], cwd=ROOT, check=True, env=env)
    new = f"finetune:models/checkpoints/phase2/graders/convnext_tiny_mixed_{head}_plain384_datasetbal_sqrtcw_v1ep_s17.pt"
    subprocess.run([sys.executable, "tools/system_eval.py", "--name", "eyepacs_grader", "--adr", "ADR-037", "--rule", "adr013", "--grader", new,
                    "--drop", "thresholds", "--apply"], cwd=ROOT, check=True, env=env)
    d = json.loads((ROOT / "queue/decisions/eyepacs_grader.json").read_text())
    record(decision="queue/decisions/eyepacs_grader.json", adopted=d.get("app_grader_switched"))
    print(f"RESULT: ADR-037 EyePACS triggered: {summary['training_images']} training images after audit "
          f"({summary['removed_for_leak']} leak matches removed); grader {'adopted' if d.get('app_grader_switched') else 'not adopted'} by ADR-013", flush=True)


if __name__ == "__main__":
    main()
