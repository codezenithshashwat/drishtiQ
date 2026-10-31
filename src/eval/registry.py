"""Append-only run registry: results/registry.csv (tracked) + results/runs/<run_id>/ details."""
import csv
import hashlib
import json
import subprocess
from datetime import datetime

from . import ROOT

RESULTS = ROOT / "results"
REGISTRY = RESULTS / "registry.csv"
LESIONS = ["MA", "HE", "EX", "SE"]
COLUMNS = (
    ["run_id", "timestamp", "task", "model", "description", "train_data", "eval_overlap", "eval_split", "n_images",
     "split_sha256", "checkpoints_sha256", "config_hash", "git_commit",
     "qwk", "qwk_ci", "macro_f1", "macro_f1_ci", "recall_g0", "recall_g1", "recall_g1_ci", "recall_g2", "recall_g3",
     "recall_g4", "severe_under", "severe_under_ci", "referable_sens", "referable_spec"]
    + [f"aupr_{l}" for l in LESIONS]
    + [f"dice_{l}" for l in LESIONS]
    + [f"threshold_{l}" for l in LESIONS]
    + [f"fp_regions_g0_{l}" for l in LESIONS]
    + ["notes"]
)


def git_commit():
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        return head + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def config_hash(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()[:12]


def checkpoints_hash(checkpoints):
    return hashlib.sha256(json.dumps(checkpoints, sort_keys=True).encode()).hexdigest()[:12]


def fmt(v):
    return "" if v is None else f"{v:.4f}" if isinstance(v, float) else str(v)


def ci(pair):
    return f"{pair[0]:.3f}-{pair[1]:.3f}"


def record(task, model, row, details, config):
    stamp = datetime.now()
    run_id = f"{stamp:%Y%m%d-%H%M%S}-{task}-{model.replace(':', '_').replace('/', '_').replace('*', 'x')[:40]}"
    folder = RESULTS / "runs" / run_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "metrics.json").write_text(json.dumps({"config": config, **details}, indent=2, default=str))
    row = {**row, "run_id": run_id, "timestamp": stamp.isoformat(timespec="seconds"), "task": task, "model": model,
           "config_hash": config_hash(config), "git_commit": git_commit()}
    new = not REGISTRY.exists()
    with REGISTRY.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="raise")
        if new:
            w.writeheader()
        w.writerow({k: fmt(row.get(k)) for k in COLUMNS})
    return run_id, folder
