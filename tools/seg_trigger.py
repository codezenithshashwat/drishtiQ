"""Conditional, per-lesion segmentation upgrades (ADR-036), run as one queue job per stage.

    .venv\\Scripts\\python tools\\seg_trigger.py --stage loss      # focal + Dice for each lesion still > 0.05 short of target
    .venv\\Scripts\\python tools\\seg_trigger.py --stage encoder   # ConvNeXt-T encoder for each lesion still > 0.05 short

For each lesion, the app's current method is looked up in configs/app/app.json and its IDRiD 5-fold CV AUPR in the
registry. A lesion more than 0.05 below its ADR-026 target triggers the stage: 5 CV folds of the variant, post-
processing re-selection (training-side CV, grade-0 FP constraint), IDRiD-val + DDR-test, then the per-lesion rule
against the app's current method (rules.py seg-swap --base-from-app --lesions L --apply). Lesions not triggered are
recorded. Every step is resumable (finished folds are skipped).
"""
import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {"MA": 0.40, "HE": 0.60, "EX": 0.80, "SE": 0.60}
MARGIN = 0.05
CKPT = "models/checkpoints/phase2/seg_a3/unet_r18_fov1536_{variant}_fold{k}_s17.pt"


def current_cv_aupr(app, lesion):
    seg = (app.get("segmenter") or {}).get(lesion) or dict(model="v0", postprocess="configs/postprocess/pp_v2.json", cv="v0-recipe-cv")
    name = f"{seg.get('cv', 'v0-recipe-cv')}+{Path(seg['postprocess']).stem}"
    rows = [r for r in csv.DictReader(open(ROOT / "results/registry.csv", encoding="utf-8"))
            if r["task"] == "segment" and r["model"] == name and r["eval_split"] == "idrid_seg_cv50_oof"]
    return (float(rows[-1][f"aupr_{lesion}"]) if rows and rows[-1][f"aupr_{lesion}"] else None), name


def run(cmd):
    print(">", " ".join(cmd), flush=True)
    subprocess.run([sys.executable, *cmd], cwd=ROOT, check=True, env={**os.environ, "PYTHONPATH": str(ROOT / "src")})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["loss", "encoder"], required=True)
    args = ap.parse_args()
    kind = "focal" if args.stage == "loss" else "enc"
    log = {}
    for lesion, target in TARGETS.items():
        app = json.loads((ROOT / "configs/app/app.json").read_text())  # re-read: an earlier lesion may have swapped
        aupr, source = current_cv_aupr(app, lesion)
        if aupr is None:
            log[lesion] = dict(triggered=False, reason=f"no CV AUPR for the current method ({source})")
            continue
        if target - aupr <= MARGIN:
            log[lesion] = dict(triggered=False, cv_aupr=aupr, target=target, reason="within 0.05 of target")
            continue
        variant = f"{kind}_{lesion}"
        for k in range(5):
            run(["src/train/seg_a3.py", "--fold", str(k), "--variant", variant])
        spec = "a3:" + CKPT.format(variant=variant, k=4)
        label, pp = f"a3{variant}-cv", f"configs/postprocess/pp_a3{variant}_v1.json"
        run(["-m", "eval.seg_pp_select", "--cache", f"results/cache/seg_a3_cv_{variant}", "--fold4-model", spec, "--label", label,
             "--fp-constraint", "--out", pp])
        for split in ("idrid_seg_val", "ddr_seg_test"):
            run(["-m", "eval", "segment", "--model", spec, "--split", split, "--postprocess", pp])
        run(["tools/rules.py", "seg-swap", "--name", f"a3{variant}_swap", "--adr", "ADR-036", "--lesions", lesion,
             "--new-cv", f"{label}+{Path(pp).stem}", "--new", f"{spec}+{Path(pp).stem}", "--new-spec", spec, "--new-pp", pp,
             "--base-from-app", "--apply"])
        d = json.loads((ROOT / f"queue/decisions/a3{variant}_swap.json").read_text())
        log[lesion] = dict(triggered=True, cv_aupr_before=aupr, target=target, variant=variant, adopted=lesion in d["lesions_swapped"],
                           cv_aupr_candidate=d["per_lesion"][lesion]["aupr"]["cv"]["a3"])
    (ROOT / f"queue/decisions/seg_trigger_{args.stage}.json").write_text(json.dumps(dict(adr="ADR-036", stage=args.stage, lesions=log), indent=2))
    print(f"RESULT: ADR-036 {args.stage} stage: " + "; ".join(
        f"{l} {'triggered, ' + ('adopted' if v['adopted'] else 'not adopted') if v['triggered'] else 'not triggered (' + v['reason'] + ')'}"
        for l, v in log.items()), flush=True)


if __name__ == "__main__":
    main()
