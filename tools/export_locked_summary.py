"""Copy the locked-evaluation headline numbers (ADR-046) into a static file the About page reads, so the page shows them
without a backend change: frontend/public/locked_results.json (served from the built page).

    .venv\\Scripts\\python tools\\export_locked_summary.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend/public/locked_results.json"


def main():
    out = {}
    for name in ("idrid_test", "deepdrid"):
        p = ROOT / f"results/locked/{name}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        g = d.get("grading") or d["primary_image_level"]["grading"]
        ri = d.get("routing_images") or d["primary_image_level"]["routing_images"]
        row = dict(set=d["set"], tag=d["tag"], commit=d["commit"][:7], n_images=d.get("n") or d.get("n_images"), n_patients=d.get("n_patients"),
                   qwk=g["qwk"], qwk_ci95=g["ci95"]["qwk"], sensitivity=g["referable_sensitivity"], specificity=g["referable_specificity"],
                   auroc=g["referable_auroc"],
                   images=dict(coverage=ri["coverage"], coverage_ci95=ri["coverage_ci95"], missed=ri["missed"], referable=ri["referable"],
                               upper95=ri["miss_rate_upper95"]))
        if "patient_level_routing" in d:
            pl = d["patient_level_routing"]
            row["patients"] = dict(coverage=pl["coverage"], coverage_ci95=pl["coverage_ci95"], missed=pl["missed"], referable=pl["referable"],
                                   upper95=pl["miss_rate_upper95"])
            row["quality_agreement"] = d["quality_gate"]["accuracy"]
            row["quality_flag_rate_among_poor"] = d["quality_gate"]["flag_rate_among_poor"]
        out[name] = row
    OUT.write_text(json.dumps(dict(source="results/locked (ADR-046)", sets=out), indent=2))
    print(f"RESULT: wrote {OUT.relative_to(ROOT)} ({', '.join(out)})")


if __name__ == "__main__":
    main()
