"""APTOS-2019 (train.csv + train_images) audit, duplicate resolution, cross-dataset leak check and frozen split.

    .venv\\Scripts\\python src\\data\\audit_aptos.py fingerprint      # hashes for APTOS and all IDRiD images
    .venv\\Scripts\\python src\\data\\audit_aptos.py audit            # duplicates, conflicts, leaks, contact sheets
    .venv\\Scripts\\python src\\data\\audit_aptos.py split            # frozen stratified train/val (85/15)

Raw data is only read. Outputs: results/audit/aptos/*.csv|json (tracked, small), contact sheets in
results/audit_images/ (untracked: they contain patient images).
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data.fingerprint import fingerprint, hamming_matrix, to_bits  # noqa: E402

RAW = ROOT / "data/raw/APTOS2019"
IDRID = ROOT / "data/raw/IDRiD/original"
OUT = ROOT / "results/audit/aptos"
SHEETS = ROOT / "results/audit_images/aptos"
SPLITS = ROOT / "configs/splits"
# 256-bit structure-hash thresholds, calibrated in src/data/calibrate_hash.py (results/audit/hash_calibration.json):
# re-saved copies of IDRiD images: median 12, p95 32, max 42; distinct IDRiD photographs: median 114, and the only
# pair <= 32 (IDRiD_013/IDRiD_397, d=22) was visually confirmed as the same eye photographed twice.
DUP_HAMMING = 32      # same photograph / same-eye capture: grouped automatically
REVIEW_HAMMING = 42   # 33-42: listed with contact sheets for manual review; for leakage checks treated as a match
SEED = 20261028


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, cols=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = cols or list(rows[0])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def quality(path):
    with Image.open(path) as im:
        small = np.asarray(im.convert("RGB").resize((512, round(512 * im.height / im.width))), np.float32)
    fov = small.max(2) > 15
    from scipy import ndimage as ndi
    if fov.mean() < 0.2:
        return dict(fov_fraction=float(fov.mean()), brightness=None, sharpness=None)
    inner = ndi.binary_erosion(fov, iterations=8)
    g = small[..., 1]
    return dict(fov_fraction=float(fov.mean()), brightness=float(g[fov].mean()),
                sharpness=float(ndi.laplace(ndi.gaussian_filter(g, 1.0))[inner].var()))


def _fp(path):
    return dict(path=str(Path(path).relative_to(ROOT)).replace("\\", "/"), **fingerprint(path), **quality(path))


def cmd_fingerprint():
    labels = {r["id_code"]: r["diagnosis"] for r in read_csv(RAW / "train.csv")}
    aptos = sorted((RAW / "train_images").glob("*.png"))
    assert len(aptos) == len(labels), (len(aptos), len(labels))
    idrid = sorted(p for p in IDRID.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif"} and "Groundtruth" not in str(p))
    with ProcessPoolExecutor(max_workers=6) as ex:
        a = list(ex.map(_fp, aptos, chunksize=16))
        b = list(ex.map(_fp, idrid, chunksize=8))
    for r, p in zip(a, aptos):
        r.update(id_code=p.stem, DR_grade=labels[p.stem])
    write_csv(OUT / "aptos_fingerprints.csv", a)
    write_csv(OUT / "idrid_all_fingerprints.csv", b)
    print(f"APTOS {len(a)}, IDRiD {len(b)} images fingerprinted")


def groups_from_pairs(n, pairs):
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, j in pairs:
        parent[find(i)] = find(j)
    g = defaultdict(list)
    for i in range(n):
        g[find(i)].append(i)
    return [v for v in g.values() if len(v) > 1]


def contact_sheet(path, items, title):
    """items: list of (image path, caption). Small thumbnails for manual review."""
    t = 160
    cols = min(len(items), 6)
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * t, rows * (t + 18) + 20), "white")
    d = ImageDraw.Draw(sheet)
    d.text((4, 4), title, fill="black")
    for k, (p, cap) in enumerate(items):
        with Image.open(ROOT / p) as im:
            im = im.convert("RGB")
            im.thumbnail((t, t))
        x, y = (k % cols) * t, 20 + (k // cols) * (t + 18)
        sheet.paste(im, (x, y))
        d.text((x + 2, y + t + 2), cap[:26], fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=80)


def cmd_audit():
    a = read_csv(OUT / "aptos_fingerprints.csv")
    b = read_csv(OUT / "idrid_all_fingerprints.csv")
    n = len(a)
    ha = to_bits([r["shash"] for r in a])
    dist = hamming_matrix(ha, ha)
    np.fill_diagonal(dist, 999)
    nearest = dist.min(1)
    pairs = [(i, j) for i, j in zip(*np.nonzero(dist <= DUP_HAMMING)) if i < j]
    exact = defaultdict(list)
    for i, r in enumerate(a):
        exact[r["sha256"]].append(i)
    pairs += [(v[0], k) for v in exact.values() for k in v[1:]]
    groups = groups_from_pairs(n, pairs)

    keep, drop, group_rows = set(range(n)), {}, []
    for gid, members in enumerate(sorted(groups, key=lambda g: -len(g))):
        grades = sorted({a[i]["DR_grade"] for i in members})
        conflict = len(grades) > 1
        if conflict:
            for i in members:
                drop[i] = "duplicate_group_conflicting_labels"
        else:
            best = max(members, key=lambda i: int(a[i]["width"]) * int(a[i]["height"]))
            for i in members:
                if i != best:
                    drop[i] = "redundant_duplicate_same_label"
        for i in members:
            group_rows.append(dict(group=gid, id_code=a[i]["id_code"], DR_grade=a[i]["DR_grade"], width=a[i]["width"], height=a[i]["height"],
                                   conflict=conflict, kept=i not in drop))
        if gid < 40:
            contact_sheet(SHEETS / f"dup_group_{gid:03d}.jpg", [(a[i]["path"], f"{a[i]['id_code'][:8]} g{a[i]['DR_grade']} {a[i]['width']}") for i in members],
                          f"group {gid} {'CONFLICT' if conflict else 'consistent'}")
    keep -= set(drop)

    # Review band (33-42): listed with contact sheets, not merged automatically.
    border = [(i, j, int(dist[i, j])) for i, j in zip(*np.nonzero((dist > DUP_HAMMING) & (dist <= REVIEW_HAMMING))) if i < j]
    for k, (i, j, dd) in enumerate(border[:24]):
        contact_sheet(SHEETS / f"review_{k:02d}_d{dd}.jpg", [(a[i]["path"], f"g{a[i]['DR_grade']}"), (a[j]["path"], f"g{a[j]['DR_grade']}")], f"hamming {dd}")
    write_csv(OUT / "aptos_review_pairs.csv", [dict(a=a[i]["id_code"], b=a[j]["id_code"], grade_a=a[i]["DR_grade"], grade_b=a[j]["DR_grade"], hamming=dd)
                                               for i, j, dd in border] or [dict(a="", b="", grade_a="", grade_b="", hamming="")])

    # Cross-dataset: exact and structure-hash matches against every IDRiD image (all tasks, all splits);
    # conservative: anything in the review band counts as a match.
    hb = to_bits([r["shash"] for r in b])
    cross = hamming_matrix(ha, hb)
    sha_b = {r["sha256"]: r["path"] for r in b}
    leaks = [dict(id_code=a[i]["id_code"], idrid_path=b[j]["path"], hamming=int(cross[i, j]), exact=a[i]["sha256"] == b[j]["sha256"])
             for i, j in zip(*np.nonzero(cross <= REVIEW_HAMMING))]
    leaks += [dict(id_code=r["id_code"], idrid_path=sha_b[r["sha256"]], hamming=0, exact=True) for r in a if r["sha256"] in sha_b and
              not any(l["id_code"] == r["id_code"] for l in leaks)]
    for k, l in enumerate(leaks[:12]):
        i = next(i for i, r in enumerate(a) if r["id_code"] == l["id_code"])
        contact_sheet(SHEETS / f"cross_idrid_{k:02d}.jpg", [(a[i]["path"], "APTOS"), (l["idrid_path"], "IDRiD")], f"hamming {l['hamming']}")
    leaked = {l["id_code"] for l in leaks}
    for i, r in enumerate(a):
        if r["id_code"] in leaked:
            drop[i] = "matches_idrid_image"
    keep -= set(drop)

    res = Counter(f"{r['width']}x{r['height']}" for r in a)
    low_quality = [r for r in a if r["sharpness"] in ("", None) or float(r["fov_fraction"]) < 0.2
                   or (r["brightness"] and float(r["brightness"]) < 25) or (r["sharpness"] and float(r["sharpness"]) < 0.5)]
    report = dict(
        images=n, grades=dict(sorted(Counter(r["DR_grade"] for r in a).items())),
        exact_duplicate_groups=sum(1 for v in exact.values() if len(v) > 1),
        hash="256-bit structure hash", dup_threshold=DUP_HAMMING, review_threshold=REVIEW_HAMMING, review_pairs=len(border),
        duplicate_groups=len(groups), images_in_duplicate_groups=sum(len(g) for g in groups),
        conflicting_groups=sum(1 for g in groups if len({a[i]["DR_grade"] for i in g}) > 1),
        dropped=dict(Counter(drop.values())), kept=len(keep),
        kept_grades=dict(sorted(Counter(a[i]["DR_grade"] for i in keep).items())),
        nearest_hamming_histogram={f"{lo}-{lo + 9}": int(((nearest >= lo) & (nearest <= lo + 9)).sum()) for lo in range(0, 120, 10)},
        resolutions_top=res.most_common(12), distinct_resolutions=len(res),
        heuristic_quality_flags=dict(count=len(low_quality), note="same heuristics as the app quality check: FOV<0.2, mean green<25, sharpness<0.5"),
        idrid_matches=len(leaks), messidor2_checked=False)
    (OUT / "aptos_audit.json").write_text(json.dumps(report, indent=2))
    write_csv(OUT / "aptos_duplicate_groups.csv", group_rows or [dict(group="", id_code="")])
    write_csv(OUT / "aptos_idrid_matches.csv", leaks or [dict(id_code="", idrid_path="", hamming="", exact="")])
    clean = [dict(id_code=a[i]["id_code"], filepath=a[i]["path"], DR_grade=a[i]["DR_grade"], content_hash=a[i]["sha256"]) for i in sorted(keep)]
    write_csv(OUT / "aptos_clean_manifest.csv", clean)
    print(json.dumps(report, indent=2))


def cmd_split():
    from sklearn.model_selection import StratifiedShuffleSplit
    targets = [SPLITS / "aptos_train.csv", SPLITS / "aptos_val.csv"]
    if any(p.exists() for p in targets):
        raise SystemExit("APTOS split already frozen")
    rows = read_csv(OUT / "aptos_clean_manifest.csv")
    y = np.array([int(r["DR_grade"]) for r in rows])
    tr, va = next(StratifiedShuffleSplit(n_splits=1, test_size=0.15, random_state=SEED).split(y, y))
    cols = ["id_code", "filepath", "DR_grade", "content_hash"]
    write_csv(targets[0], [rows[i] for i in sorted(tr)], cols)
    write_csv(targets[1], [rows[i] for i in sorted(va)], cols)
    print("train", dict(sorted(Counter(y[tr].tolist()).items())), "val", dict(sorted(Counter(y[va].tolist()).items())))


if __name__ == "__main__":
    {"fingerprint": cmd_fingerprint, "audit": cmd_audit, "split": cmd_split}[sys.argv[1]]()

