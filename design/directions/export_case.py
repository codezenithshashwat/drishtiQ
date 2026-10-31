"""Export one dev-train case through the live pipeline for the static design directions.
Writes design/directions/data/ (git-ignored: contains a fundus image): base.jpg, <lesion>.png, cam.png, case.js.
    .venv\\Scripts\\python design\\directions\\export_case.py IDRiD_012
"""
import base64
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from inference import Pipeline  # noqa: E402
from inference.glossary import TERMS  # noqa: E402

OUT = Path(__file__).parent / "data"


def main(image_id):
    rows = list(csv.DictReader(open(ROOT / "configs/splits/idrid_grading_devtrain.csv", newline="", encoding="utf-8")))
    row = next(r for r in rows if r["image_id"] == image_id)  # dev-train only: never locked test or Messidor-2
    res = Pipeline().analyze((ROOT / row["filepath"]).read_bytes())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "base.jpg").write_bytes(base64.b64decode(res.pop("display_image")))
    for l in res["lesions"]:
        (OUT / f"{l['key']}.png").write_bytes(base64.b64decode(l.pop("overlay")))
    (OUT / "cam.png").write_bytes(base64.b64decode(res["attribution"].pop("overlay")))
    res["source"] = dict(image_id=image_id, split="idrid_grading_devtrain", reference_grade=int(row["DR_grade"]))
    (OUT / "case.js").write_text("window.CASE = " + json.dumps(res) + ";\nwindow.GLOSSARY = " + json.dumps(TERMS) + ";\n", encoding="utf-8")
    print(image_id, "grade", res["grading"]["grade"], "explanations", len(res["explanations"]))


if __name__ == "__main__":
    main(sys.argv[1])
