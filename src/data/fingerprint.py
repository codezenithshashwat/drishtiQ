"""Image fingerprints for duplicate and leakage checks: exact SHA-256 of file bytes and a 64-bit DCT perceptual hash.

The pHash is computed on the field-of-view crop (black border removed, padded square) so that the same photograph
saved at another resolution, crop margin or JPEG quality maps to a nearby hash.
"""
import hashlib
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.fft import dctn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from inference.preprocess import crop_to_fov  # noqa: E402

POPCOUNT = np.array([bin(i).count("1") for i in range(256)], np.uint8)


def detail(im):
    """64x64 high-pass green-channel map of the FOV crop: illumination removed, vessels and lesions kept."""
    g = np.asarray(crop_to_fov(im.convert("RGB")).resize((256, 256), Image.Resampling.BILINEAR), np.float32)[..., 1]
    d = g - ndi.gaussian_filter(g, 8)
    yy, xx = np.ogrid[:256, :256]
    d[(xx - 127.5) ** 2 + (yy - 127.5) ** 2 > 118 ** 2] = 0  # drop the FOV edge ring
    return np.asarray(Image.fromarray(d).resize((64, 64), Image.Resampling.BILINEAR))


def structure_hash(im):
    """256-bit DCT hash of the retina's *structure*.

    A plain grey-level pHash is not discriminative for fundus photos: at 32x32 every image is an orange disc on
    black. The hash uses a 16x16 block of low-frequency DCT coefficients (DC row/column excluded) of `detail`.
    """
    block = dctn(detail(im), norm="ortho")[1:17, 1:17].ravel()
    return np.packbits(block > np.median(block)).tobytes().hex()


def detail_correlation(im_a, im_b, max_shift=3):
    """Peak Pearson correlation of two detail maps over small translations (confirms a hash candidate pair)."""
    a, b = detail(im_a), detail(im_b)
    best = -1.0
    for dy in range(-max_shift, max_shift + 1):
        for dx in range(-max_shift, max_shift + 1):
            x = a[max(dy, 0):64 + min(dy, 0), max(dx, 0):64 + min(dx, 0)].ravel()
            y = b[max(-dy, 0):64 + min(-dy, 0), max(-dx, 0):64 + min(-dx, 0)].ravel()
            best = max(best, float(np.corrcoef(x, y)[0, 1]))
    return best


def fingerprint(path):
    raw = Path(path).read_bytes()
    with Image.open(path) as im:
        im.load()
        return dict(sha256=hashlib.sha256(raw).hexdigest(), shash=structure_hash(im), width=im.width, height=im.height, mode=im.mode)


def to_bits(hexes):
    """Hex structure hashes -> (n, 32) uint8 array."""
    return np.frombuffer(b"".join(bytes.fromhex(h) for h in hexes), np.uint8).reshape(len(hexes), -1)


def hamming_matrix(a, b, block=1024):
    """Pairwise Hamming distances between two (n, bytes) uint8 hash arrays."""
    out = np.empty((len(a), len(b)), np.uint16)
    for i in range(0, len(a), block):
        out[i:i + block] = POPCOUNT[a[i:i + block, None, :] ^ b[None, :, :]].sum(-1, dtype=np.uint16)
    return out
