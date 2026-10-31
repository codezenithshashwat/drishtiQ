"""S1 (ADR-027): regression thresholds that maximise macro-F1 on the fine-tuner's inner hold-out (never on validation).

    .venv\Scripts\python tools\s1_thresholds.py

Coordinate search on a 0.01 grid within +-0.5 of each current threshold, repeated until no threshold moves.
Writes configs/grading/s1_thresholds.json; tools/system_eval.py then applies the ADR-027 rule.
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from pseudo_label import inner_holdout_scores  # noqa: E402
from inference.finetuned import FinetunedGrader  # noqa: E402

OUT = ROOT / "configs/grading/s1_thresholds.json"


def macro_f1(scores, y, t):
    return f1_score(y, np.searchsorted(np.sort(t), scores, side="right"), labels=range(5), average="macro", zero_division=0)


def main():
    app = json.loads((ROOT / "configs/app/app.json").read_text())
    grader = FinetunedGrader(sorted(glob.glob(str(ROOT / app["grader"].removeprefix("finetune:")))))
    s, y, _ = inner_holdout_scores(grader)
    t = np.array(grader.thresholds, dtype=float)
    start = macro_f1(s, y, t)
    for _ in range(20):
        moved = False
        for k in range(4):
            grid = np.round(np.arange(t[k] - 0.5, t[k] + 0.501, 0.01), 3)
            lo = t[k - 1] + 0.01 if k else -np.inf
            hi = t[k + 1] - 0.01 if k < 3 else np.inf
            best = max((g for g in grid if lo <= g <= hi), key=lambda g: (macro_f1(s, y, np.r_[t[:k], g, t[k + 1:]]), -abs(g - t[k])))
            if best != t[k]:
                t[k], moved = best, True
        if not moved:
            break
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dict(adr="ADR-027", grader=app["grader"], thresholds=t.tolist(), previous=list(map(float, grader.thresholds)),
                                   inner_macro_f1=dict(before=start, after=macro_f1(s, y, t)), fitted_on=f"inner hold-out ({len(y)})"), indent=2))
    print(f"RESULT: S1 thresholds {np.round(t, 3).tolist()} (inner macro-F1 {start:.3f} -> {macro_f1(s, y, t):.3f})", flush=True)


if __name__ == "__main__":
    main()
