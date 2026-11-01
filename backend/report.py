"""B7 reports: a doctor report (English) and a patient summary (English or Hindi) for one patient, from the latest case
per eye. One Jinja2 template renders both the on-screen preview and the PDF. The PDF is printed by headless Microsoft
Edge, which shapes Devanagari correctly (Nirmala UI), so no PDF library is needed.
"""
import base64
import io
import json
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image

from .report_text import PATIENT

ROOT = Path(__file__).resolve().parents[1]
TOKENS = json.loads((ROOT / "design/tokens.json").read_text())
FONTS = ROOT / "frontend/node_modules/@fontsource/inter/files"
EDGE = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"), Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]
env = Environment(loader=FileSystemLoader(ROOT / "backend/templates"), autoescape=select_autoescape(["html"]))
GRADE_SHORT = ["No apparent DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "Proliferative DR"]


def composite(analysis, width=520):
    """Display image with the lesion overlays the app shows, as a JPEG data URI."""
    def decode(b64):
        return Image.open(io.BytesIO(base64.b64decode(b64.split(",", 1)[-1])))
    im = decode(analysis["display_image"]).convert("RGBA")
    for lesion in analysis.get("lesions", []):
        im.alpha_composite(decode(lesion["overlay"]).convert("RGBA").resize(im.size))
    im = im.convert("RGB")
    im.thumbnail((width, width))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def eye_rows(cases, summary=None):
    """One row per photographed eye of the visit. `eff` is the effective (clinician-authoritative) state of that eye from
    backend/clinical_state.py; the AI fields stay labelled as suggestions in the template."""
    eff = {e["eye"]: e.get("effective") for e in (summary or {}).get("eyes", [])}
    rows = []
    for c in cases:
        a, s = c["analysis"], c["assist"]
        row = dict(id=c["id"], eye=c["eye"], ok=a.get("status") == "ok", assist=s, route=c.get("routing"), image=composite(a) if a.get("display_image") else None,
                   quality=a.get("quality", {}), review=c.get("review"), eff=eff.get(c["eye"]))
        if row["ok"]:
            f = a["findings"]
            row.update(stage=a["grading"]["grade"], stage_label=GRADE_SHORT[a["grading"]["grade"]], dme=f["macular_edema_risk"],
                       lesions={k: v["count"] for k, v in f["lesions"].items()},
                       sentences=[x for x in a.get("explanations", []) if x["section"] in ("summary", "evidence", "macula")],
                       flags=[x for x in a.get("explanations", []) if x["section"] == "flags"])
        rows.append(row)
    return rows


def render(kind, lang, patient_ref, cases, summary, model_version, font_base="/report-fonts/"):
    if kind == "patient" and lang not in PATIENT:
        raise ValueError(f"unsupported language {lang}")
    tpl = env.get_template("report.html")
    return tpl.render(kind=kind, lang=lang if kind == "patient" else "en", t=PATIENT[lang if kind == "patient" else "en"],
                      c=TOKENS["color"], patient_ref=patient_ref, today=date.today().isoformat(), eyes=eye_rows(cases, summary),
                      summary=summary, model_version=model_version, font_base=font_base, brand=TOKENS["brand_identity"],
                      missing=(summary.get("effective") or {}).get("missing_eyes", []) if not summary.get("single_photo") else [])


def edge_path():
    return next((p for p in EDGE if p.exists()), None) or (shutil.which("msedge") and Path(shutil.which("msedge")))


def pdf(html_text):
    """HTML -> PDF bytes via headless Edge (separate throwaway profile)."""
    edge = edge_path()
    if not edge:
        raise RuntimeError("Microsoft Edge not found; PDF export unavailable")
    with tempfile.TemporaryDirectory(dir=ROOT / "data/app", ignore_cleanup_errors=True) as tmp:  # Edge may hold files briefly
        src, out = Path(tmp) / "report.html", Path(tmp) / "report.pdf"
        src.write_text(html_text.replace('url("/report-fonts/', f'url("{FONTS.as_uri()}/'), encoding="utf-8")
        subprocess.run([str(edge), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={Path(tmp) / 'profile'}",
                        "--no-first-run", f"--print-to-pdf={out}", src.as_uri()], capture_output=True, timeout=90, check=False)
        if not out.exists():
            raise RuntimeError("Edge did not produce a PDF")
        return out.read_bytes()
