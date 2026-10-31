"""List / extract the DDR lesion-segmentation subset from the 10-part archive (plain byte split of one zip).

    .venv\\Scripts\\python src\\data\\extract_ddr.py list
    .venv\\Scripts\\python src\\data\\extract_ddr.py extract     # lesion_segmentation/ only; CRC-32 checked; read-only
"""
import io
import json
import os
import stat
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data.extract_mmrdr import MultiPart  # noqa: E402

ARCHIVE = ROOT / "data/raw/DDR/archive"
DEST = ROOT / "data/raw/DDR"
OUT = ROOT / "results/audit/ddr"
KEEP = "lesion_segmentation/"


def open_archive():
    parts = sorted(ARCHIVE.glob("DDR-dataset.zip.0*"))
    assert len(parts) == 10, parts
    return zipfile.ZipFile(io.BufferedReader(MultiPart(parts), buffer_size=8 << 20))


def cmd_list():
    with open_archive() as z:
        infos = z.infolist()
    by = Counter("/".join(i.filename.split("/")[:4]) for i in infos if not i.is_dir())
    summary = dict(members=len(infos), bytes=sum(i.file_size for i in infos), by_folder=dict(sorted(by.items())),
                   keep_members=sum(1 for i in infos if KEEP in i.filename and not i.is_dir()),
                   keep_bytes=sum(i.file_size for i in infos if KEEP in i.filename))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "archive_listing.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


def cmd_extract():
    with open_archive() as z:
        members = [i for i in z.infolist() if KEEP in i.filename and not i.is_dir()]
        for k, info in enumerate(members):
            rel = info.filename[info.filename.index(KEEP):]
            target = (DEST / rel).resolve()
            assert target.is_relative_to(DEST.resolve()), info.filename
            if target.exists() and target.stat().st_size == info.file_size:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as dst:
                while block := src.read(1 << 20):
                    dst.write(block)  # zipfile raises BadZipFile on a CRC-32 mismatch
            os.chmod(target, stat.S_IREAD)
            if k % 500 == 0:
                print(f"{k}/{len(members)}", flush=True)
    print(f"extracted {len(members)} members (CRC-32 verified)")


if __name__ == "__main__":
    {"list": cmd_list, "extract": cmd_extract}[sys.argv[1]]()
