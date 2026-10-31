"""Extract only MMRDR-CFP/ from the verified 9-part MMRDR archive, without concatenating parts on disk.

The parts (MMRDR.zip.001-009) are a plain byte split of one zip file; a seekable reader spans them.
    .venv\\Scripts\\python src\\data\\extract_mmrdr.py list      # member summary, no extraction
    .venv\\Scripts\\python src\\data\\extract_mmrdr.py extract   # extract MMRDR-CFP only, then mark files read-only
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
ARCHIVE = ROOT / "data/raw/MMRDR/archive"
DEST = ROOT / "data/raw/MMRDR"
OUT = ROOT / "results/audit/mmrdr"
PREFIX = "MMRDR-CFP/"


class MultiPart(io.RawIOBase):
    def __init__(self, parts):
        self.parts = [open(p, "rb") for p in parts]
        self.sizes = [os.path.getsize(p) for p in parts]
        self.starts = [sum(self.sizes[:i]) for i in range(len(parts))]
        self.total = sum(self.sizes)
        self.pos = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.total + offset}[whence]
        return self.pos

    def readinto(self, b):
        n, view = 0, memoryview(b)
        while n < len(view) and self.pos < self.total:
            i = max(k for k, s in enumerate(self.starts) if s <= self.pos)
            f = self.parts[i]
            f.seek(self.pos - self.starts[i])
            chunk = f.read(min(len(view) - n, self.sizes[i] - (self.pos - self.starts[i])))
            view[n:n + len(chunk)] = chunk
            n += len(chunk)
            self.pos += len(chunk)
        return n

    def close(self):
        for f in self.parts:
            f.close()
        super().close()


def open_archive():
    parts = sorted(ARCHIVE.glob("MMRDR.zip.0*"))
    assert len(parts) == 9, parts
    return zipfile.ZipFile(io.BufferedReader(MultiPart(parts), buffer_size=8 << 20))


def top(name, depth=2):
    return "/".join(name.split("/")[:depth])


def cmd_list():
    with open_archive() as z:
        infos = z.infolist()
    summary = dict(members=len(infos), by_folder=dict(Counter(top(i.filename) for i in infos).most_common(40)),
                   cfp_members=sum(1 for i in infos if PREFIX in i.filename),
                   cfp_bytes=sum(i.file_size for i in infos if PREFIX in i.filename),
                   cfp_non_images=[i.filename for i in infos if PREFIX in i.filename and not i.filename.lower().endswith((".jpg", ".jpeg", ".png", "/"))])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "archive_listing.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


def cmd_extract():
    with open_archive() as z:
        members = [i for i in z.infolist() if PREFIX in i.filename and not i.is_dir()]
        root = members[0].filename.split(PREFIX)[0]
        for k, info in enumerate(members):
            rel = info.filename[len(root):]
            target = (DEST / rel).resolve()
            assert target.is_relative_to(DEST.resolve()), info.filename  # no path traversal
            if target.exists() and target.stat().st_size == info.file_size:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as dst:
                while block := src.read(1 << 20):
                    dst.write(block)  # zipfile verifies each member's CRC-32 on read
            os.chmod(target, stat.S_IREAD)
            if k % 1000 == 0:
                print(f"{k}/{len(members)}", flush=True)
    print(f"extracted {len(members)} members under {DEST / PREFIX}")


if __name__ == "__main__":
    {"list": cmd_list, "extract": cmd_extract}[sys.argv[1]]()
