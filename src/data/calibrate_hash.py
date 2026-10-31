"""Calibrate the two-stage duplicate rule: structure-hash candidate threshold + detail-correlation confirmation.

Negatives: all pairs among the 404 clean IDRiD grading-train images (verified distinct photographs).
Positives: 80 of those images re-saved the way public datasets re-host images (downscaled to 1504/1050/640 px,
JPEG q70-90, crop margin changed, brightness +-10%), compared with their original.
Writes results/audit/hash_calibration.json.
"""
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data.fingerprint import detail_correlation, hamming_matrix, structure_hash, to_bits  # noqa: E402
from eval import data  # noqa: E402

OUT = ROOT / "results/audit/hash_calibration.json"


def resave(im, rng):
    w = int(rng.choice([1050, 640, 1504]))
    im = im.resize((w, round(w * im.height / im.width)), Image.Resampling.LANCZOS)
    m = int(rng.integers(0, 40))
    im = im.crop((m, m // 2, im.width - m, im.height - m // 2))
    im = ImageEnhance.Brightness(im).enhance(float(rng.uniform(0.9, 1.1)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=int(rng.integers(70, 91)))
    return Image.open(buf)


def rule():
    """(hash candidate threshold, correlation confirmation threshold) from the saved calibration."""
    c = json.loads(OUT.read_text())
    return c["hash_threshold"], c["correlation_threshold"]


def main():
    rng = np.random.default_rng(0)
    rows = data.read_csv(data.GRADING_TRAIN_MANIFEST)
    ims = [data.load_image(r["filepath"]) for r in rows]
    for im in ims:
        im.thumbnail((1600, 1600))  # hash/detail use a 256 px FOV crop; this only saves memory
    hashes = to_bits([structure_hash(im) for im in ims])
    d = hamming_matrix(hashes, hashes).astype(int)
    iu = np.triu_indices(len(rows), 1)
    neg = d[iu]
    pos, pos_corr = [], []
    for i in rng.choice(len(rows), 80, replace=False):
        copy = resave(ims[i], rng)
        pos.append(int(hamming_matrix(hashes[i:i + 1], to_bits([structure_hash(copy)]))[0, 0]))
        pos_corr.append(detail_correlation(ims[i], copy))
    hash_threshold = int(max(pos))  # every re-saved copy becomes a candidate
    close = [(i, j) for i, j in zip(*iu) if d[i, j] <= 60]  # distinct pairs that look closest to the hash
    neg_corr = [detail_correlation(ims[i], ims[j]) for i, j in close]
    corr_threshold = round((min(pos_corr) + max(neg_corr)) / 2, 3) if min(pos_corr) > max(neg_corr) else round(float(np.percentile(pos_corr, 1)), 3)
    report = dict(
        hash_bits=256, hash_threshold=hash_threshold, correlation_threshold=corr_threshold,
        negatives=dict(pairs=len(neg), hash_min=int(neg.min()), hash_median=float(np.median(neg)),
                       at_or_below_hash_threshold=int((neg <= hash_threshold).sum()),
                       close_pairs_checked=len(close), close_pairs_max_correlation=round(max(neg_corr), 4),
                       confirmed_false_duplicates=int(sum(c >= corr_threshold for (i, j), c in zip(close, neg_corr) if d[i, j] <= hash_threshold))),
        positives=dict(n=len(pos), hash_median=float(np.median(pos)), hash_max=int(max(pos)),
                       correlation_min=round(min(pos_corr), 4), correlation_median=round(float(np.median(pos_corr)), 4),
                       missed=int(sum(c < corr_threshold for c in pos_corr))),
        rule="duplicate iff structure-hash Hamming <= hash_threshold AND peak detail correlation >= correlation_threshold")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
