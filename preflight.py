"""Pre-start checklist for the local app. Prints PASS / WARN / FAIL per check; exit code 1 if anything FAILs.

    .venv\\Scripts\\python preflight.py            # check
    .venv\\Scripts\\python preflight.py --record   # record SHA-256 of every model/config file the app loads

Recorded checksums live in configs/app/checksums.json; a changed or missing file is a FAIL. start.ps1 runs this first.
"""
import argparse
import glob
import hashlib
import importlib
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "configs/app/app.json"
MANIFEST = ROOT / "configs/app/checksums.json"
results = []


def check(name, status, detail=""):
    results.append((status, name, detail))
    print(f"[{status:4}] {name}{': ' + detail if detail else ''}", flush=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def app_files():
    """Every model and config file the app loads, from configs/app/app.json."""
    app = json.loads(APP.read_text())
    files = [APP]
    g = app["grader"]
    if g.startswith("finetune:"):
        for p in sorted(glob.glob(str(ROOT / g.removeprefix("finetune:")))):
            files += [Path(p), Path(p).with_suffix(".json")]
    elif g == "v0":
        sys.path.insert(0, str(ROOT / "src"))
        from inference.pipeline import CKPT, GRADER_HEADS
        files += [CKPT / h for h in GRADER_HEADS]
    seg = app.get("segmenter") or {k: dict(model="v0", postprocess="configs/postprocess/pp_v2.json") for k in ("MA", "HE", "EX", "SE")}
    for v in seg.values():
        files.append(ROOT / v["postprocess"])
        if v["model"] == "v0":
            files += [ROOT / "models/checkpoints/model_selection/seg_Segformer_full512_bce_dice_s17.pt",
                      ROOT / "models/checkpoints/model_selection/ma_Unet_full512_weighted_bce_tversky_e12_s17_fp32.pt"]
        elif v["model"].split(":")[0] in ("a3", "a3tta", "a3ens"):
            sys.path.insert(0, str(ROOT / "src"))
            from inference.a3_segmenter import paths_for
            for p in paths_for(v["model"])[0]:
                files += [Path(p), Path(p).with_suffix(".json")]
    sysc = app.get("system") or {}
    if sysc.get("thresholds"):
        files.append(ROOT / sysc["thresholds"])
    for ckpt in (sysc.get("specialists") or {}).values():
        files += [ROOT / ckpt, (ROOT / ckpt).with_suffix(".json")]
    for key in ("dme_rule", "fusion"):
        if app.get(key):
            files.append(ROOT / app[key])
    for extra in ("configs/landmarks/fovea_v1.json", "configs/quality/quality_v1.json", "configs/calibration/app_grader.json",
                  "review/hindi_review.csv", "design/tokens.json"):
        if (ROOT / extra).exists():
            files.append(ROOT / extra)
    return sorted(set(files), key=str)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    if args.record:
        MANIFEST.write_text(json.dumps({str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p) for p in app_files()}, indent=2))
        print(f"recorded {len(app_files())} checksums in {MANIFEST.relative_to(ROOT)}")
        return

    print("RetinaScreen preflight\n")
    ok = sys.version_info >= (3, 10)
    check("Python", "PASS" if ok else "FAIL", f"{sys.version.split()[0]} at {sys.executable}")
    missing = []
    for mod in ("torch", "timm", "segmentation_models_pytorch", "fastapi", "uvicorn", "PIL", "sklearn", "scipy", "jinja2", "numpy"):
        try:
            importlib.import_module(mod)
        except Exception as e:  # noqa: BLE001 (any import failure is a missing package)
            missing.append(f"{mod} ({type(e).__name__})")
    check("Python packages", "FAIL" if missing else "PASS", ", ".join(missing) or "all present")

    try:
        import torch
        if torch.cuda.is_available():
            check("GPU", "PASS", torch.cuda.get_device_name(0))
        else:
            check("GPU", "WARN", "no CUDA GPU; the app runs on the CPU (slower, see README)")
    except Exception as e:  # noqa: BLE001
        check("GPU", "WARN", f"could not query CUDA ({e})")

    try:
        files = app_files()
        absent = [str(p.relative_to(ROOT)) for p in files if not p.exists()]
        check("Model and config files", "FAIL" if absent else "PASS", f"missing: {absent}" if absent else f"{len(files)} files present")
        if MANIFEST.exists():
            recorded = json.loads(MANIFEST.read_text())
            changed = [k for k, v in recorded.items() if (ROOT / k).exists() and sha256(ROOT / k) != v]
            gone = [k for k in recorded if not (ROOT / k).exists()]
            unrecorded = [str(p.relative_to(ROOT)).replace("\\", "/") for p in files if str(p.relative_to(ROOT)).replace("\\", "/") not in recorded]
            bad = changed + gone
            check("Checksums", "FAIL" if bad else "WARN" if unrecorded else "PASS",
                  f"changed or missing: {bad}" if bad else f"not recorded yet: {unrecorded}" if unrecorded else f"{len(recorded)} files match")
        else:
            check("Checksums", "WARN", "none recorded yet (run: preflight.py --record)")
    except Exception as e:  # noqa: BLE001
        check("Model and config files", "FAIL", f"configs/app/app.json unreadable ({e})")

    app = json.loads(APP.read_text())
    cal = ROOT / "configs/calibration/app_grader.json"
    cal_ok = cal.exists() and json.loads(cal.read_text()).get("grader") == app["grader"] and not app.get("fusion")
    check("Calibration", "PASS" if cal_ok else "WARN", "fitted for the current grader" if cal_ok else "not fitted for the current grader; probabilities will show as pending")

    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        head = ""
    if not head and (ROOT / "BUILD_COMMIT").exists():  # copy without git history (project zip)
        head = (ROOT / "BUILD_COMMIT").read_text().strip()
    info = ROOT / "frontend/dist/build-info.json"
    built = json.loads(info.read_text())["commit"] if info.exists() else None
    check("Frontend build", "PASS" if built and built == head else "FAIL",
          f"built from {built}, code at {head}" + ("" if built == head else " (rebuild: cd frontend && npm run build)"))

    with socket.socket() as s:
        busy = s.connect_ex(("127.0.0.1", args.port)) == 0
    check(f"Port {args.port}", "WARN" if busy else "PASS", "in use (an app instance may already be running)" if busy else "free")

    edge = [p for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe") if Path(p).exists()]
    check("PDF export", "PASS" if edge else "WARN", "Microsoft Edge found (server-side PDF)" if edge else "Edge not found; use Print / Save as PDF")

    free = shutil.disk_usage(ROOT).free / 2**30
    check("Disk space", "PASS" if free > 5 else "WARN", f"{free:.0f} GB free")

    fails = [r for r in results if r[0] == "FAIL"]
    print(f"\n{'FAIL' if fails else 'PASS'}: {len(results) - len(fails)} of {len(results)} checks without failure")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
