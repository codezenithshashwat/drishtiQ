"""Step 6 timing (measurement only, no optimisation): per-stage and per-patient latency on GPU and CPU, peak RAM / VRAM.

    .venv\\Scripts\\python tools\\benchmark.py

Images: 10 IDRiD dev-train images (seed 17), used as 5 synthetic patients (two images = right + left eye); the first
image is a warm-up and not timed. Per stage: quality check, grading + Grad-CAM, optic disc, fovea, lesion segmentation,
and the rest of the analysis (overlays, findings, explanations). Per patient: both eyes posted through the HTTP API
(analysis + store + routing + patient aggregation) and the patient report rendered, in a throwaway store.
Each device runs in its own subprocess; the CPU child sets RS_DEVICE=cpu (the GPU stays visible to the driver but unused;
hiding it with CUDA_VISIBLE_DEVICES=-1 crashes with this driver, ADR-044). Writes results/benchmark.json.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
STAGES = ("quality", "grading_gradcam", "optic_disc", "fovea", "segmentation")


def measure(device):
    import psutil
    import torch
    from eval import data
    from inference import pipeline as P
    if device == "cpu":
        assert os.environ.get("RS_DEVICE") == "cpu"
    rows = data.load_split("idrid_grading_devtrain")[0]
    picks = [rows[i] for i in np.random.default_rng(17).choice(len(rows), 11, replace=False)]
    images = [(ROOT / r["filepath"]).read_bytes() for r in picks]
    proc = psutil.Process()
    t0 = time.perf_counter()
    pipe = P.Pipeline(device=device)
    load_s = time.perf_counter() - t0
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()

    timer = {}

    def timed(name, fn):
        def wrap(*a, **k):
            t = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                timer[name] = timer.get(name, 0.0) + time.perf_counter() - t
        return wrap

    pipe.quality = timed("quality", P.Pipeline.quality)
    pipe.grader.grade_with_cam = timed("grading_gradcam", pipe.grader.grade_with_cam)
    P.pp.locate_optic_disc = timed("optic_disc", P.pp.locate_optic_disc)
    P.landmarks.fovea = timed("fovea", P.landmarks.fovea)
    pipe.segmenter.masks = timed("segmentation", pipe.segmenter.masks)

    pipe.analyze(images[0])  # warm-up
    per_image = []
    for b in images[1:]:
        timer.clear()
        t = time.perf_counter()
        pipe.analyze(b)
        total = time.perf_counter() - t
        per_image.append(dict(total=total, **{s: timer.get(s, 0.0) for s in STAGES}, rest=total - sum(timer.values())))
    stages = {k: dict(mean_s=float(np.mean([p[k] for p in per_image])), max_s=float(np.max([p[k] for p in per_image])))
              for k in ("total", *STAGES, "rest")}
    del pipe

    # Per patient through the HTTP API (two eyes + routing + patient report), throwaway store
    from fastapi.testclient import TestClient
    from backend import store
    from backend.app import app
    store.DIR = Path(tempfile.mkdtemp())
    store.IMAGES = store.DIR / "images"
    patients = []
    with TestClient(app) as c:
        c.post("/api/cases", files={"file": ("w.jpg", images[0], "image/jpeg")}, data={"patient_ref": "WARM", "eye": "right"})
        for n in range(5):
            t = time.perf_counter()
            for eye, b in (("right", images[1 + 2 * n]), ("left", images[2 + 2 * n])):
                r = c.post("/api/cases", files={"file": ("f.jpg", b, "image/jpeg")}, data={"patient_ref": f"BENCH-{n}", "eye": eye})
                assert r.status_code == 200, r.text[:200]
            assert c.get(f"/api/patients/BENCH-{n}/report.html?kind=doctor&lang=en").status_code == 200
            patients.append(time.perf_counter() - t)
    peak_ram = proc.memory_info().peak_wset if hasattr(proc.memory_info(), "peak_wset") else proc.memory_info().rss
    return dict(device=device, model_load_s=load_s, images_timed=len(per_image), per_stage=stages,
                per_patient_two_eyes=dict(patients=len(patients), mean_s=float(np.mean(patients)), max_s=float(np.max(patients))),
                peak_ram_mib=peak_ram / 2**20,
                peak_vram_allocated_mib=torch.cuda.max_memory_allocated() / 2**20 if device == "cuda" else None,
                cuda_visible=torch.cuda.is_available() if device == "cuda" else False)


def child(device):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    if device == "cpu":
        env["RS_DEVICE"] = "cpu"  # not CUDA_VISIBLE_DEVICES=-1: unstable with this driver (ADR-044)
    r = subprocess.run([sys.executable, __file__, f"--{device}-child"], env=env, capture_output=True, text=True, cwd=ROOT)
    return json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": f"exit {r.returncode}: {r.stderr[-800:]}"}


def main():
    if len(sys.argv) > 1 and sys.argv[1].endswith("-child"):
        print(json.dumps(measure(sys.argv[1][2:].removesuffix("-child"))))
        return
    out = dict(gpu=child("cuda"), cpu=child("cpu"), app=json.loads((ROOT / "configs/app/app.json").read_text())["version"],
               note="Measurement only, no optimisation. 10 IDRiD dev-train images (5 synthetic two-eye patients) after one warm-up.")
    (ROOT / "results/benchmark.json").write_text(json.dumps(out, indent=2))
    for d in ("gpu", "cpu"):
        v = out[d]
        print(f"RESULT {d}: " + (f"image {v['per_stage']['total']['mean_s']:.2f} s, patient {v['per_patient_two_eyes']['mean_s']:.2f} s, "
                                 f"peak RAM {v['peak_ram_mib']:.0f} MiB" if "error" not in v else v["error"][:200]), flush=True)


if __name__ == "__main__":
    main()
