"""FastAPI backend for the DR screening decision-support prototype.

Run from the project root:
    .venv\\Scripts\\python -m uvicorn backend.app:app --port 8000
/api/analyze processes an image in memory only. /api/cases stores the image and its analysis locally (backend/store.py)
for the worklist, reviews and reports. On start-up, stored cases analysed with other models are re-analysed in the
background, so the worklist always reflects the models in configs/app/app.json.
"""
import base64
import csv
import io
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")  # every weight file is local; the app never downloads at run time
from inference import Pipeline, assist, findings, routing  # noqa: E402

from . import experiments, report, store  # noqa: E402

MAX_BYTES = 25 * 1024 * 1024
MIN_SIDE = 256
ALLOWED = {"JPEG": "jpg", "PNG": "png", "TIFF": "tif", "BMP": "bmp"}
FRONTEND = ROOT / "frontend" / "dist"
state = {}


def git_commit():
    """Short commit of the code on disk; outside a git checkout, the stamp in BUILD_COMMIT (None if neither)."""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = ""
    stamp = ROOT / "BUILD_COMMIT"
    return commit or (stamp.read_text().strip() if stamp.exists() else None)


def signature(pipeline):
    """What a stored analysis must match to be current: app version, grader, segmenter, fusion, macular-edema rule and
    quality gate."""
    app_cfg = json.loads((ROOT / "configs/app/app.json").read_text())
    from inference.pipeline import CORNER_DARK_MIN
    return json.dumps(dict(version=pipeline.model_version, grader=app_cfg["grader"], segmenter=app_cfg.get("segmenter"),
                           fusion=app_cfg.get("fusion"), dme_rule=findings.DME_RULE, quality_corner_dark_min=CORNER_DARK_MIN), sort_keys=True)


def reanalyse_stale():
    db, pipeline, sig = state["db"], state["pipeline"], state["signature"]
    stale = [r for r in store.cases(db) if r["analysed_with"] != sig]
    state["reanalysis"] = dict(total=len(stale), done=0)
    for r in stale:
        try:
            store.update_analysis(db, r["id"], pipeline.analyze(store.image_bytes(r)), sig)
        except Exception as e:  # one unreadable stored image must not stop the others
            print(f"re-analysis of {r['id']} failed: {e}", flush=True)
        state["reanalysis"]["done"] += 1


def pipeline():
    """The loaded pipeline, or a plain 503 when start-up failed (e.g. a model file is missing)."""
    if "pipeline" not in state:
        raise HTTPException(503, state.get("startup_error", "The models are still loading. Try again in a minute."))
    return state["pipeline"]


@asynccontextmanager
async def lifespan(app):
    state["commit"] = git_commit()
    try:
        state["pipeline"] = Pipeline()
    except Exception as e:  # missing or corrupt model file, broken config: report it instead of crashing
        traceback.print_exc()
        state["startup_error"] = (f"The app could not load its models ({type(e).__name__}: {e}). Run preflight.py to see which file is "
                                  "missing or changed.")
        state.update(db=store.connect(), signature="", calibration=None)  # the worklist stays readable
        yield
        state.clear()
        return
    state["signature"] = signature(state["pipeline"])
    state["db"] = store.connect()
    # ADR-019 calibration was fitted on the grader score; it does not apply to a fused stage (ADR-021).
    p = state["pipeline"]
    stage_changed = p.fusion or (p.system is not None and p.system.changes_stage)
    state["calibration"] = None if stage_changed else assist.load_calibration(p.system.name if p.system else p.grader_spec)
    state["routing_valid"] = routing.routing_valid(p.grader_spec, p.checkpoints, p.system is not None, bool(p.fusion))
    threading.Thread(target=reanalyse_stale, daemon=True).start()
    yield
    state.clear()


app = FastAPI(title="DR Screening Decision Support (prototype)", version="0.2.0", lifespan=lifespan)


@app.get("/api/health")
def health():
    p = state.get("pipeline")
    status = "ok" if p else "error" if state.get("startup_error") else "loading"
    return {"status": status, "device": p.device if p else None, "error": state.get("startup_error"), "reanalysis": state.get("reanalysis")}


@app.get("/api/glossary")
def glossary():
    from inference.glossary import TERMS
    return TERMS


@app.get("/api/version")
def version():
    """Which code and models this process runs. The frontend compares `commit` with its own build commit and
    `commit_on_disk`, and shows a "backend is outdated" banner when they differ (a process started before a merge
    once served new screens against old routes and answered 405)."""
    p = pipeline()  # 503 with the start-up error, if any
    return {"model_version": p.model_version, "commit": state.get("commit"), "commit_on_disk": git_commit(),
            "grader": p.grader_spec, "calibrated": state.get("calibration") is not None, "device": p.device,
            "checkpoints_sha256": p.checkpoints}


async def read_image(file):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image is larger than 25 MB.")
    if not data:
        raise HTTPException(400, "Empty upload.")
    try:
        with Image.open(io.BytesIO(data)) as im:
            fmt, size = im.format, im.size
            im.verify()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, "File is not a readable image (JPEG, PNG, TIFF or BMP).")
    if fmt not in ALLOWED:
        raise HTTPException(415, f"Unsupported image format {fmt}; use JPEG, PNG, TIFF or BMP.")
    if min(size) < MIN_SIDE:
        raise HTTPException(422, f"Image is too small ({size[0]}x{size[1]}); at least {MIN_SIDE} px per side is needed.")
    return data, ALLOWED[fmt]


def run(data):
    """Analyse with plain-language errors; a GPU out-of-memory error is retried once on the CPU."""
    import torch
    start = time.perf_counter()
    try:
        result = pipeline().analyze(data)
    except torch.cuda.OutOfMemoryError:
        torch.cuda.empty_cache()
        if "cpu_pipeline" not in state:
            state["cpu_pipeline"] = Pipeline(device="cpu")
        result = state["cpu_pipeline"].analyze(data)
        result["device_fallback"] = "The graphics card ran out of memory, so this image was analysed on the CPU (slower)."
    except (OSError, SyntaxError, ValueError) as e:  # truncated or corrupt image data that passed the header check
        raise HTTPException(422, f"The image could not be decoded ({type(e).__name__}). Re-export it as JPEG or PNG and try again.")
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(500, "The analysis failed unexpectedly. The details are in the backend log; try another image or restart the app.")
    result["processing_seconds"] = round(time.perf_counter() - start, 3)
    return result


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    data, _ = await read_image(file)
    return run(data)


# ---- cases (worklist, case view, reviews) -------------------------------------------------------------------------
THUMBS = {}


def thumbnail(cid, analysis):
    if cid not in THUMBS and analysis.get("display_image"):
        im = Image.open(io.BytesIO(base64.b64decode(analysis["display_image"].split(",", 1)[-1])))
        im.thumbnail((96, 96))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=80)
        THUMBS[cid] = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    return THUMBS.get(cid)


def target():
    """Operating point: target referable miss rate (ADR-040; default 2.5%, configurable to 5%)."""
    return float(store.settings().get("target", routing.load_config()["default_target"]))


def signed_referral(review):
    """A signed review that refers the eye: corrected stage >= 2, or agreement with an AI stage >= 2."""
    if not review:
        return False
    stage = review["corrected_stage"] if review["decision"] == "disagree" else review["ai_stage"] if review["decision"] == "agree" else None
    return stage is not None and stage >= 2


def eye_routing(r, a, s):
    """Eye state + reasons (routing.eye_state) and the previous signed result for this patient's eye."""
    previous, prior_referral, retakes = None, None, 0
    for e in store.earlier_cases(state["db"], r):
        ea = json.loads(e["analysis"])
        if e["eye"] in ("right", "left") and (ea.get("status") != "ok" or not ea["quality"]["usable"]) and not previous:
            retakes += 1
        rev = store.reviews(state["db"], e["id"])
        if rev and previous is None:
            previous = dict(case_id=e["id"], created=e["created"], reviewer=rev[0]["reviewer"], decision=rev[0]["decision"],
                            ai_stage=rev[0]["ai_stage"], corrected_stage=rev[0]["corrected_stage"], note=rev[0]["note"])
            if signed_referral(rev[0]):
                prior_referral = f"case {e['id']}, {e['created'][:10]}"
    intake = dict(vision_problems=bool(r["vision_problems"]), prior_treatment=bool(r["prior_treatment"]))
    out = routing.eye_state(a, eye=r["eye"], target=target(), valid=state.get("routing_valid", False),
                            stage_confidence=s.get("stage_confidence"), intake=intake, prior_referral=prior_referral, retakes=retakes)
    return dict(**out, label=routing.LABEL[out["state"]], previous=previous, intake=intake)


def summary_row(r):
    a = json.loads(r["analysis"])
    s = assist.annotate(a, state["calibration"])
    route = eye_routing(r, a, s)
    ok = a.get("status") == "ok"
    return dict(id=r["id"], created=r["created"], patient_ref=r["patient_ref"], eye=r["eye"], status=r["status"], source=r["source"],
                stale=r["analysed_with"] != state["signature"], assist=s, thumbnail=thumbnail(r["id"], a),
                stage=a["grading"]["grade"] if ok else None, stage_label=a["grading"]["label"] if ok else None,
                dme=a["findings"]["macular_edema_risk"]["level"] if ok else None, quality_usable=a["quality"]["usable"],
                lesion_regions=sum(l["components"] for l in a.get("lesions", [])), flags=a.get("consistency_flags", []), routing=route)


@app.get("/api/cases")
def list_cases():
    rows = [summary_row(r) for r in store.cases(state["db"])]
    # ADR-040 order: URGENT_REVIEW -> CLINICIAN_REVIEW -> REFERABLE -> RETAKE -> ROUTINE; within a group, higher P(referable) first.
    rows.sort(key=lambda x: (x["status"] == "reviewed", routing.ORDER[x["routing"]["state"]], -(x["assist"].get("p_referable") or 0.0)))
    return dict(cases=rows, calibration=dict(available=state["calibration"] is not None, tau=(state["calibration"] or {}).get("tau")),
                reanalysis=state.get("reanalysis"))


def full_case(r):
    a = json.loads(r["analysis"])
    s = assist.annotate(a, state["calibration"])
    return dict(id=r["id"], created=r["created"], patient_ref=r["patient_ref"], eye=r["eye"], status=r["status"], source=r["source"],
                stale=r["analysed_with"] != state["signature"], analysis=a, assist=s, routing=eye_routing(r, a, s),
                reviews=store.reviews(state["db"], r["id"]))


@app.post("/api/cases")
async def create_case(file: UploadFile = File(...), patient_ref: str = Form(..., min_length=1, max_length=40),
                      eye: str = Form(..., pattern="^(right|left|unknown)$"), vision_problems: bool = Form(False),
                      prior_treatment: bool = Form(False)):
    data, ext = await read_image(file)
    result = run(data)
    cid = store.add_case(state["db"], patient_ref.strip(), eye, "upload", data, ext, result, state["signature"],
                         intake=dict(vision_problems=vision_problems, prior_treatment=prior_treatment))
    return case_payload(cid)


def case_payload(cid):
    """The complete case record (with the patient-level summary) that every case endpoint returns."""
    r = store.case(state["db"], cid)
    if not r:
        raise HTTPException(404, f"No case {cid}.")
    out = full_case(r)
    out["patient"] = patient_payload(r["patient_ref"])["summary"]
    return out


@app.get("/api/cases/{cid}")
def get_case(cid: str):
    return case_payload(cid)


class Review(BaseModel):
    reviewer: str = Field(min_length=1, max_length=60)
    decision: str = Field(pattern="^(agree|disagree|ungradable)$")
    corrected_stage: int | None = Field(default=None, ge=0, le=4)
    corrected_dme: str | None = Field(default=None, pattern="^(low|possible|high)$")
    note: str = Field(default="", max_length=1000)


@app.post("/api/cases/{cid}/review")
def review_case(cid: str, body: Review):
    r = store.case(state["db"], cid)
    if not r:
        raise HTTPException(404, f"No case {cid}.")
    a = json.loads(r["analysis"])
    if body.decision == "disagree" and body.corrected_stage is None:
        raise HTTPException(422, "A disagreement needs the corrected stage.")
    store.add_review(state["db"], cid, body.reviewer, body.decision, body.corrected_stage, body.corrected_dme, body.note,
                     a["grading"]["grade"] if a.get("status") == "ok" else None, pipeline().grader_spec)
    return case_payload(cid)


@app.get("/api/disagreements")
def disagreements():
    """Reviews in which the clinician changed the AI's stage, newest first (the doctor-feedback view)."""
    out = []
    for r in reversed(store.reviews(state["db"])):
        if r["decision"] != "disagree":
            continue
        c = store.case(state["db"], r["case_id"])
        out.append(dict(review_id=r["id"], case_id=r["case_id"], created=r["created"], reviewer=r["reviewer"], ai_stage=r["ai_stage"],
                        corrected_stage=r["corrected_stage"], corrected_dme=r["corrected_dme"], note=r["note"], ai_grader=r["ai_grader"],
                        patient_ref=c["patient_ref"] if c else None, eye=c["eye"] if c else None))
    return dict(disagreements=out, reviews_total=len(store.reviews(state["db"])))


@app.get("/api/feedback.csv")
def feedback_csv():
    rows = store.reviews(state["db"])
    buf = io.StringIO()
    cols = ["id", "case_id", "created", "reviewer", "decision", "ai_stage", "corrected_stage", "corrected_dme", "note", "ai_grader"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=feedback.csv"})


# ---- patient-level output and reports (B7) --------------------------------------------------------------------------
def patient_payload(patient_ref):
    rows = store.patient_cases(state["db"], patient_ref)
    if not rows:
        raise HTTPException(404, f"No cases for patient {patient_ref}.")
    cases = []
    for r in rows:
        c = full_case(r)
        c["review"] = c["reviews"][0] if c["reviews"] else None
        cases.append(c)
    summary = routing.patient_state([dict(eye=c["eye"], state=c["routing"]["state"], reasons=c["routing"]["reasons"],
                                          stage=c["analysis"]["grading"]["grade"] if c["analysis"].get("status") == "ok" else None) for c in cases])
    level = {routing.URGENT: "urgent", routing.REFERABLE: "refer", routing.ROUTINE: "routine", routing.RETAKE: "retake",
             routing.INCOMPLETE: "incomplete"}.get(summary["state"], "human")
    worst = max(cases, key=lambda c: routing.SEVERITY[c["routing"]["state"]])
    text = " ".join(summary["notes"] or worst["routing"]["reasons"])
    summary.update(follow_up=dict(level=level, title=summary["label"], text=text),
                   note="Suggested by the prototype from the AI output; the clinician decides.",
                   eyes=[dict(eye=c["eye"], case_id=c["id"], stage=c["analysis"]["grading"]["grade"] if c["analysis"].get("status") == "ok" else None,
                              label=c["analysis"].get("grading", {}).get("label"), state=c["routing"]["state"], state_label=c["routing"]["label"],
                              reasons=c["routing"]["reasons"], defer=c["routing"]["state"] != routing.ROUTINE,
                              p_referable=c["assist"].get("p_referable")) for c in cases],
                   operating_point=dict(target=target(), wording=routing.wording(target()), valid=state.get("routing_valid", False)))
    return dict(cases=cases, summary=summary)


class Settings(BaseModel):
    target: float = Field(description="target referable miss rate: 0.025 (default) or 0.05")


@app.get("/api/settings")
def get_settings():
    cfg = routing.load_config()
    return dict(target=target(), choices=[float(k) for k in cfg["thresholds"]], wording=routing.wording(target()),
                routing_valid=state.get("routing_valid", False))


@app.post("/api/settings")
def set_settings(body: Settings):
    if f"{body.target}" not in routing.load_config()["thresholds"]:
        raise HTTPException(422, "The operating point must be 0.025 or 0.05 (the thresholds fitted on the internal hold-out).")
    store.save_settings(dict(target=body.target))
    return get_settings()


def report_html(patient_ref, kind, lang):
    if kind not in ("doctor", "patient") or lang not in ("en", "hi"):
        raise HTTPException(422, "kind must be doctor or patient; lang must be en or hi.")
    p = patient_payload(patient_ref)
    return report.render(kind, lang, patient_ref, p["cases"], p["summary"], pipeline().model_version)


@app.get("/api/patients/{patient_ref}/report.html", response_class=HTMLResponse)
def report_preview(patient_ref: str, kind: str = "doctor", lang: str = "en"):
    return report_html(patient_ref, kind, lang)


@app.get("/api/patients/{patient_ref}/report.pdf")
def report_pdf(patient_ref: str, kind: str = "doctor", lang: str = "en"):
    try:
        data = report.pdf(report_html(patient_ref, kind, lang))
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    name = f"{patient_ref}_{kind}{'' if kind == 'doctor' else '_' + lang}.pdf"
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---- about the model ------------------------------------------------------------------------------------------------
def registry_rows():
    with open(ROOT / "results/registry.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def latest(rows, model, split, task=None):
    hits = [r for r in rows if r["model"] == model and r["eval_split"] == split and (task is None or r["task"] == task)]
    return hits[-1] if hits else None


# "Models we compared": fixed comparisons with matched training data; the numbers are read from the registry.
COMPARED = [
    dict(model="EfficientNet-B3 (fine-tuned, 384 px)", setting="IDRiD dev-train only, regression head",
         spec="finetune:models/checkpoints/phase1/graders/efficientnet_b3_reg_ben_graham384_bnfrozen_v1_s17.pt",
         decision="Not chosen: lower agreement than ConvNeXt-T under the same recipe and unstable BatchNorm statistics.", ref="registry (phase-1 screen)"),
    dict(model="ConvNeXt-T (fine-tuned, 384 px)", setting="IDRiD dev-train only, regression head",
         spec="finetune:models/checkpoints/phase1/graders/convnext_tiny_reg_ben_graham384_v1_s17.pt",
         decision="Better than EfficientNet-B3 on the same data; IDRiD-only training generalised poorly to APTOS.", ref="registry (phase-1 screen)"),
    dict(model="RETFound ViT-L (frozen, linear probe)", setting="IDRiD + APTOS, frozen backbone",
         spec="feathead:models/checkpoints/phase2/feathead/retfound_cfp_idrid+aptos_v1_s*.pt",
         decision="Not adopted: the gain over ConvNeXt was within noise (ΔQWK CI included 0); fine-tuning a ViT-L does not fit the 4 GB GPU.", ref="ADR-012"),
    dict(model="ConvNeXt-T (frozen, linear probe)", setting="IDRiD + APTOS, frozen backbone",
         spec="feathead:models/checkpoints/phase2/feathead/convnext_tiny_in1k_idrid+aptos_v1_s*.pt",
         decision="Comparator for RETFound.", ref="ADR-012"),
    dict(model="ConvNeXt-T (fine-tuned, 384 px), chosen", setting="IDRiD + APTOS + MMRDR, regression head",
         spec="finetune:models/checkpoints/phase2/graders/convnext_tiny_mixed_reg_plain384_datasetbal_sqrtcw_v1_s17.pt",
         decision="Adopted by the pre-registered paired-bootstrap rule.", ref="ADR-013, ADR-015"),
]


@app.get("/api/model")
def model_card():
    app_cfg = json.loads((ROOT / "configs/app/app.json").read_text())
    rows = registry_rows()
    grader = app_cfg["grader"]
    sysname = pipeline().system.name if pipeline().system else grader  # registry name of the grading system (ADR-033)

    def grade_metrics(split):
        r = latest(rows, sysname, split, task="grade")
        if not r:
            return None
        m = json.loads((ROOT / "results/runs" / r["run_id"] / "metrics.json").read_text())
        return dict(run_id=r["run_id"], n=int(r["n_images"]), point=m["point"], ci95=m.get("ci95"), confusion=m.get("confusion"),
                    seconds_per_image=m.get("seconds_per_image"))

    def agreement(split):
        """Exact / within-one-stage agreement row computed from a registered run of the app grader on this split."""
        hits = [r for r in rows if r["task"] == "agreement" and r["model"] == sysname and r["eval_split"] == split]
        if not hits:
            return None
        m = json.loads((ROOT / "results/runs" / hits[-1]["run_id"] / "metrics.json").read_text())
        return dict(run_id=hits[-1]["run_id"], source_run=m["source_run"], point=m["point"], ci95=m["ci95"])

    def coverage():
        """Routine-rescreening coverage (ADR-039 Step 2) from its registered run; levels from the same run's metrics."""
        hits = [r for r in rows if r["task"] == "coverage"]
        if not hits:
            return None
        m = json.loads((ROOT / "results/runs" / hits[-1]["run_id"] / "metrics.json").read_text())
        cfg = routing.load_config()
        keep = ("units", "referable", "routed", "coverage", "coverage_ci95", "missed", "miss_rate_upper95", "sensitivity", "specificity")
        return dict(run_ids=sorted({r["run_id"] for r in hits}), policy=cfg["policy"], target=target(), wording=routing.wording(target()),
                    valid=state.get("routing_valid", False), thresholds=cfg["thresholds"],
                    sets={name: {lvl: {k: v["c"][lvl][k] for k in keep} for lvl in cfg["thresholds"]} for name, v in m["validation"].items()},
                    rule_of_three=m["rule_of_three"], patient_level=m["patient_level"])

    decisions = {}
    folder = ROOT / "queue/decisions"
    for p in sorted(folder.glob("*.json")) if folder.exists() else []:
        decisions[p.stem] = json.loads(p.read_text())
    seg_cfg = app_cfg.get("segmenter")
    seg_models = sorted({f"{v['model']}+{Path(v['postprocess']).stem}" for v in seg_cfg.values()}) if seg_cfg else ["v0+pp_v2"]
    keep = lambda r: None if r is None else {k: r[k] for k in r if k.startswith(("aupr_", "dice_", "fp_regions")) or k in ("run_id", "n_images")}
    seg = {m: {s: keep(latest(rows, m, s, task="segment")) for s in ("idrid_seg_val", "ddr_seg_test")} for m in seg_models}
    dme = json.loads((ROOT / findings.DME_RULE).read_text())
    ckpt_info = {}
    if grader.startswith("finetune:"):
        import glob
        paths = sorted(glob.glob(str(ROOT / grader.removeprefix("finetune:"))))
        info = json.loads(Path(paths[0]).with_suffix(".json").read_text())
        ckpt_info = dict(members=len(paths), description=info["description"], train_data=info["train_data"], inner_qwk=info.get("inner_qwk"))
    return dict(version=pipeline().model_version, grader=grader, system_name=sysname, system=app_cfg.get("system"), grader_info=ckpt_info, history=app_cfg.get("history", []),
                segmenter=seg_cfg or {k: dict(model="v0", postprocess="configs/postprocess/pp_v2.json") for k in ("MA", "HE", "EX", "SE")},
                grading=dict(idrid_val=grade_metrics("idrid_grading_val"), aptos_val=grade_metrics("aptos_val")),
                agreement=dict(idrid_val=agreement("idrid_grading_val"), aptos_val=agreement("aptos_val")),
                segmentation=seg, dme_rule=dict(file=findings.DME_RULE, min_exudate_area_px=dme["min_exudate_area_px"], val=dme["val"]),
                compared=[dict(**{k: v for k, v in c.items() if k != "spec"},
                               **{key: (lambda r: None if r is None else dict(qwk=float(r["qwk"]), run_id=r["run_id"]))(latest(rows, c["spec"], split, task="grade"))
                                  for key, split in (("idrid_val", "idrid_grading_val"), ("aptos_val", "aptos_val"))}) for c in COMPARED],
                calibration=state["calibration"], coverage=coverage(), experiments=experiments.rows(), decisions={k: v for k, v in decisions.items() if k in ("a2_swap", "a2_ensemble", "a3_swap")},
                checkpoints=pipeline().checkpoints)


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"], include_in_schema=False)
def api_not_found(path: str):
    """Unknown API paths get a JSON 404 for every method; they must never fall through to the page catch-all."""
    raise HTTPException(404, f"No API endpoint /api/{path}. If the app was just updated, restart the backend.")


app.mount("/report-fonts", StaticFiles(directory=report.FONTS), name="report-fonts")

if FRONTEND.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Unknown API path.")
        target = (FRONTEND / path).resolve()
        if path and target.is_file() and target.is_relative_to(FRONTEND.resolve()):
            return FileResponse(target)
        return FileResponse(FRONTEND / "index.html")
