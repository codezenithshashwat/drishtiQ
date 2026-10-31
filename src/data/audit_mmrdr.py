"""MMRDR-CFP audit: labels, lesion flags, provided tr/ts split, resolutions, duplicates and cross-dataset overlap.

    .venv\\Scripts\\python src\\data\\audit_mmrdr.py fingerprint
    .venv\\Scripts\\python src\\data\\audit_mmrdr.py audit        # needs APTOS + IDRiD fingerprints from audit_aptos.py

MMRDR-CFP is derived from OIA-DDR and is training-side only; its tr/ts split is image-level (no patient IDs).
"""
import ast
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data.audit_aptos import (DUP_HAMMING, REVIEW_HAMMING, contact_sheet, groups_from_pairs, read_csv,  # noqa: E402
                              write_csv, _fp)
from data.fingerprint import hamming_matrix, to_bits  # noqa: E402

RAW = ROOT / "data/raw/MMRDR/MMRDR-CFP"
OUT = ROOT / "results/audit/mmrdr"
SHEETS = ROOT / "results/audit_images/mmrdr"
LESIONS = ["MA", "hard_exudate", "IRH", "VB_IRMA", "NV", "vitreous_haem", "retinal_detachment"]


def labels():
    rows = []
    for r in read_csv(RAW / "FP.csv"):
        flags = ast.literal_eval(r["lesion"])
        assert len(flags) == 7
        rows.append(dict(image=r["image"], split=Path(r["image"]).name[:2], DR_grade=int(r["grade"]), lr=r["lr"],
                         **{f"les_{n}": int(v) for n, v in zip(LESIONS, flags)}))
    return rows


def cmd_fingerprint():
    rows = labels()
    paths = [RAW / r["image"] for r in rows]
    with ProcessPoolExecutor(max_workers=4) as ex:
        fps = list(ex.map(_fp, paths, chunksize=32))
    for r, f in zip(rows, fps):
        r.update(f)
    write_csv(OUT / "mmrdr_cfp_fingerprints.csv", rows)
    print(f"{len(rows)} MMRDR-CFP images fingerprinted")


def cmd_audit():
    rows = read_csv(OUT / "mmrdr_cfp_fingerprints.csv")
    n = len(rows)
    grade = np.array([int(r["DR_grade"]) for r in rows])
    split = np.array([r["split"] for r in rows])
    flags = {l: np.array([int(r[f"les_{l}"]) for r in rows]) for l in LESIONS}

    by_split = {s: dict(sorted(Counter(grade[split == s].tolist()).items())) for s in ("tr", "ts")}
    prevalence = {l: {g: round(float(flags[l][grade == g].mean()), 3) for g in range(5)} for l in LESIONS}
    # Clinical consistency of image-level flags with the ICDR grade (counts of suspicious combinations).
    any_lesion = np.any([flags[l] for l in LESIONS], 0)
    checks = dict(grade0_with_any_lesion=int((any_lesion & (grade == 0)).sum()),
                  grade_ge1_with_no_lesion=int((~any_lesion & (grade >= 1)).sum()),
                  NV_or_VH_below_grade4=int(((flags["NV"] | flags["vitreous_haem"]).astype(bool) & (grade < 4)).sum()),
                  grade4_without_NV_or_VH=int((~(flags["NV"] | flags["vitreous_haem"]).astype(bool) & (grade == 4)).sum()))

    h = to_bits([r["shash"] for r in rows])
    pairs = []
    for i in range(0, n, 2000):  # blockwise to bound memory
        d = hamming_matrix(h[i:i + 2000], h)
        for a, b in zip(*np.nonzero(d <= DUP_HAMMING)):
            if i + a < b:
                pairs.append((i + a, int(b)))
    sha = defaultdict(list)
    for i, r in enumerate(rows):
        sha[r["sha256"]].append(i)
    pairs += [(v[0], k) for v in sha.values() for k in v[1:]]
    groups = groups_from_pairs(n, pairs)
    cross_split = [g for g in groups if len({split[i] for i in g}) > 1]
    conflicting = [g for g in groups if len({grade[i] for i in g}) > 1]
    for k, g in enumerate(cross_split[:10]):
        contact_sheet(SHEETS / f"cross_split_{k:02d}.jpg", [(rows[i]["path"], f"{Path(rows[i]['image']).name} g{grade[i]}") for i in g], "tr/ts duplicate")

    external = {}
    for name, path in (("IDRiD_all", ROOT / "results/audit/aptos/idrid_all_fingerprints.csv"),
                       ("APTOS_train", ROOT / "results/audit/aptos/aptos_fingerprints.csv")):
        other = read_csv(path)
        ho = to_bits([r["shash"] for r in other])
        matches = []
        for i in range(0, n, 2000):
            d = hamming_matrix(h[i:i + 2000], ho)
            matches += [(i + a, int(b), int(d[a, b])) for a, b in zip(*np.nonzero(d <= REVIEW_HAMMING))]
        osha = {r["sha256"] for r in other}
        external[name] = dict(phash_matches=len(matches), exact_matches=sum(r["sha256"] in osha for r in rows),
                              examples=[dict(mmrdr=rows[a]["image"], other=other[b]["path"], hamming=dd) for a, b, dd in matches[:20]])
        for k, (a, b, dd) in enumerate(matches[:6]):
            contact_sheet(SHEETS / f"vs_{name}_{k:02d}.jpg", [(rows[a]["path"], "MMRDR"), (other[b]["path"], name)], f"hamming {dd}")

    res = Counter(f"{r['width']}x{r['height']}" for r in rows)
    report = dict(images=n, split_counts=dict(Counter(split.tolist())), grades_by_split=by_split,
                  grades_total=dict(sorted(Counter(grade.tolist()).items())),
                  paper_grades_total={0: 6579, 1: 1302, 2: 1959, 3: 603, 4: 675},
                  laterality=dict(Counter(r["lr"] for r in rows)),
                  lesion_flag_prevalence_by_grade=prevalence, label_consistency_checks=checks,
                  duplicate_groups=len(groups), images_in_duplicate_groups=sum(len(g) for g in groups),
                  cross_split_duplicate_groups=len(cross_split), conflicting_label_groups=len(conflicting),
                  exact_duplicate_groups=sum(1 for v in sha.values() if len(v) > 1),
                  resolutions_top=res.most_common(10), distinct_resolutions=len(res),
                  cross_dataset=external, messidor2_checked=False,
                  ddr_segmentation_overlap="not checked: DDR not downloaded")
    (OUT / "mmrdr_cfp_audit.json").write_text(json.dumps(report, indent=2))
    write_csv(OUT / "mmrdr_cfp_duplicate_groups.csv",
              [dict(group=k, image=rows[i]["image"], split=split[i], DR_grade=grade[i]) for k, g in enumerate(groups) for i in g]
              or [dict(group="", image="", split="", DR_grade="")])
    print(json.dumps({k: v for k, v in report.items() if k != "cross_dataset"}, indent=2))
    print(json.dumps({k: {m: x for m, x in v.items() if m != "examples"} for k, v in external.items()}, indent=2))


if __name__ == "__main__":
    {"fingerprint": cmd_fingerprint, "audit": cmd_audit}[sys.argv[1]]()

