"""Grading and segmentation metrics."""
import numpy as np
from scipy import ndimage as ndi
from sklearn.metrics import cohen_kappa_score, confusion_matrix, f1_score

GRADES = list(range(5))
BINS = 1000  # probability histogram resolution for pixel-level PR curves


# ---- grading ----------------------------------------------------------------------------------
def _point(y, pred):
    recall = {}
    for k in GRADES:
        m = y == k
        recall[k] = float((pred[m] == k).mean()) if m.any() else float("nan")
    severe = y >= 3
    referable = y >= 2
    return dict(
        qwk=float(cohen_kappa_score(y, pred, labels=GRADES, weights="quadratic")),
        macro_f1=float(f1_score(y, pred, labels=GRADES, average="macro", zero_division=0)),
        accuracy=float((y == pred).mean()),
        within_one=float((np.abs(y - pred) <= 1).mean()),  # exact or one stage off
        **{f"recall_g{k}": v for k, v in recall.items()},
        # Clinically dangerous: true severe NPDR / PDR predicted as no or mild DR.
        severe_under=float((pred[severe] <= 1).mean()) if severe.any() else float("nan"),
        referable_sens=float((pred[referable] >= 2).mean()) if referable.any() else float("nan"),
        referable_spec=float((pred[~referable] < 2).mean()) if (~referable).any() else float("nan"),
    )


def grading_metrics(y, probs, n_boot=2000, seed=0):
    y = np.asarray(y, int)
    pred = np.asarray(probs).argmax(1)
    point = _point(y, pred)
    rng = np.random.default_rng(seed)
    boot = {k: [] for k in point}
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        for k, v in _point(y[i], pred[i]).items():
            boot[k].append(v)
    ci = {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in boot.items()}
    return dict(point=point, ci95=ci, n=int(len(y)), support={k: int((y == k).sum()) for k in GRADES},
                confusion=confusion_matrix(y, pred, labels=GRADES).tolist(), bootstrap=n_boot)


# ---- segmentation -----------------------------------------------------------------------------
class PixelPR:
    """Accumulates positive/negative probability histograms over all pixels of all images (pooled),
    the convention of the IDRiD challenge lesion-segmentation AUPR."""

    def __init__(self):
        self.pos = np.zeros(BINS, np.int64)
        self.neg = np.zeros(BINS, np.int64)

    def add(self, prob, truth):
        idx = np.minimum((prob * BINS).astype(np.int32), BINS - 1)
        self.pos += np.bincount(idx[truth], minlength=BINS)
        self.neg += np.bincount(idx[~truth], minlength=BINS)

    def _counts(self):
        tp = np.cumsum(self.pos[::-1])[::-1]  # tp[b] = positives with prob >= b/BINS
        fp = np.cumsum(self.neg[::-1])[::-1]
        return tp, fp, self.pos.sum()

    def aupr(self):
        tp, fp, p = self._counts()
        if p == 0:
            return float("nan")
        tp, fp = tp[::-1], fp[::-1]  # thresholds from high to low
        precision = np.where(tp + fp > 0, tp / np.maximum(tp + fp, 1), 1.0)
        recall = tp / p
        return float(np.sum(np.diff(np.concatenate([[0.0], recall])) * precision))

    def dice_at(self, threshold):
        tp, fp, p = self._counts()
        b = min(int(threshold * BINS), BINS - 1)
        return float(2 * tp[b] / max(2 * tp[b] + fp[b] + (p - tp[b]), 1))

    def precision_recall_at(self, threshold):
        tp, fp, p = self._counts()
        b = min(int(threshold * BINS), BINS - 1)
        return float(tp[b] / max(tp[b] + fp[b], 1)), float(tp[b] / max(p, 1))

    def best_dice(self):
        tp, fp, p = self._counts()
        dice = 2 * tp / np.maximum(2 * tp + fp + (p - tp), 1)
        b = int(dice.argmax())
        return float(dice[b]), b / BINS


def count_regions(mask):
    return int(ndi.label(mask, np.ones((3, 3)))[1])
