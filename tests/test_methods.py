"""Unit tests for the pure parts of the pre-registered methods (CPU only; the GPU runs happen in the queue)."""
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/train"))
sys.path.insert(0, str(ROOT / "tools"))


def test_corn_score_and_loss():
    from finetune_special import corn_loss
    from inference.finetuned import corn_score
    big = torch.full((1, 4), 20.0)
    assert abs(float(corn_score(big)[0]) - 4.0) < 1e-4 and abs(float(corn_score(-big)[0])) < 1e-4  # all "greater" -> 4; none -> 0
    logits = torch.zeros(3, 4, requires_grad=True)
    loss = corn_loss(logits, torch.tensor([0, 2, 4]))
    loss.backward()
    assert torch.isfinite(loss) and logits.grad is not None and abs(float(loss) - np.log(2)) < 1e-5


def test_harmonic_inpaint_fills_only_the_mask():
    from faithfulness import control_mask, harmonic_inpaint
    img = np.zeros((40, 40, 3), np.uint8)
    img[:, :20] = 200
    mask = np.zeros((40, 40), bool)
    mask[15:25, 15:25] = True
    out = harmonic_inpaint(img, mask, iters=50)
    assert (out[~mask] == img[~mask]).all() and 0 < out[mask].mean() < 200
    fov = np.ones((60, 60), bool)
    lesions = np.zeros((60, 60), bool)
    lesions[:10, :10] = True
    m = control_mask(fov, lesions, 200, np.random.default_rng(0), radius=4)
    assert m.sum() >= 200 and not (m & lesions).any()


def test_lcn_green_shape_and_range():
    from inference.a3_segmenter import lcn_green
    sq = (np.random.default_rng(0).random((64, 64, 3)) * 255).astype(np.uint8)
    out = lcn_green(sq)
    assert out.shape == sq.shape and out.dtype == np.uint8 and (out[..., 0] == out[..., 1]).all()


def test_system_eval_rules():
    from system_eval import rule
    def d(qwk_lo, f1_lo=0.0, g1_lo=0.0, g4_lo=0.0, sev_lo=-0.01):
        mk = lambda lo: dict(point=lo + 0.01, ci95=[lo, lo + 0.02])
        return dict(qwk=mk(qwk_lo), macro_f1=mk(f1_lo), recall_g1=mk(g1_lo), recall_g4=mk(g4_lo), severe_under=mk(sev_lo))
    ok = {"idrid_grading_val": d(0.01), "aptos_val": d(-0.04)}
    assert rule("adr013", ok)["passed"]
    assert not rule("adr013", {"idrid_grading_val": d(0.01), "aptos_val": d(-0.06)})["passed"]
    assert rule("s1", {"idrid_grading_val": d(-0.01, f1_lo=0.01), "aptos_val": d(-0.01)})["passed"]
    assert not rule("s1", {"idrid_grading_val": d(-0.03, f1_lo=0.01), "aptos_val": d(-0.01)})["passed"]
    assert rule("g1", {"idrid_grading_val": d(-0.01), "aptos_val": d(-0.01, g1_lo=0.02)})["passed"]
    assert not rule("g4", {"idrid_grading_val": d(-0.01), "aptos_val": d(-0.01, g4_lo=-0.01)})["passed"]
    assert not rule("g1", {"idrid_grading_val": d(-0.01, sev_lo=0.01), "aptos_val": d(-0.01, g1_lo=0.02)})["passed"]


def test_s1_macro_f1_search_improves_on_a_toy_set():
    from s1_thresholds import macro_f1
    rng = np.random.default_rng(0)
    y = rng.integers(0, 5, 500)
    s = y + rng.normal(0, 0.4, 500) + 0.3  # biased scores: shifted thresholds should help
    assert macro_f1(s, y, np.array([0.8, 1.8, 2.8, 3.8])) > macro_f1(s, y, np.array([0.5, 1.5, 2.5, 3.5]))


def test_segmentation_loss_variants():
    from seg_a3 import bce_part, focal_term, loss_fn
    torch.manual_seed(0)
    logits, y = torch.randn(2, 4, 16, 16), (torch.rand(2, 4, 16, 16) > 0.9).float()
    valid = torch.ones(2, 4)
    assert abs(float(bce_part(logits, y, valid)) - float(loss_fn(logits, y, valid)) + 0) > 0  # loss_fn = BCE + Dice > BCE
    f = focal_term(logits, y, valid, "MA")
    assert torch.isfinite(f) and float(f) < float(bce_part(logits[:, :1], y[:, :1], valid[:, :1])) + 1e-6  # focal <= BCE


def test_variant_transforms():
    from inference.a3_segmenter import TRANSFORM_OF, VARIANTS
    assert TRANSFORM_OF["ma_lcn"] == "ma_lcn" and all(TRANSFORM_OF[v] == "base" for v in VARIANTS if v.startswith(("focal_", "enc_")))


def test_deepdrid_aggregation_rules():
    """ADR-035: max-score image per eye; unusable image -> the other; both unusable -> deferred; patient = worse eye."""
    from external_eval import aggregate
    def r(i, grade, stage, score, usable=True):
        return dict(id=i, grade=grade, stage=stage, score=score, p_ref=score / 4, status="ok", usable=usable)
    recs = [r("1_l1", 0, 0, 0.2), r("1_l2", 0, 1, 1.1),            # eye 1L: max score -> stage 1
            r("1_r1", 3, 3, 2.9), r("1_r2", 3, 0, 0.1),            # eye 1R: stage 3 (worse eye -> patient referable)
            r("2_l1", 2, 2, 2.0, usable=False), r("2_l2", 2, 1, 1.2),  # unusable image ignored -> stage 1
            r("2_r1", 0, 0, 0.0, usable=False), r("2_r2", 0, 0, 0.0, usable=False),  # both unusable -> deferred
            r("3_l1", 0, 0, 0.1), r("3_l2", 0, 0, 0.2), r("3_r1", 1, 1, 1.0), r("3_r2", 1, 1, 0.9)]
    out = aggregate(recs)
    e, p = out["eye_level"], out["patient_level"]
    assert e["n_eyes"] == 6 and e["deferred_eyes"] == 1 and e["n_graded"] == 5
    assert p["n_patients"] == 3 and p["referable_sens"] == 0.5 and p["referable_spec"] == 1.0  # patient 2 referable truth, AI says stage 1
