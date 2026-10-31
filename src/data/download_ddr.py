"""Download the 10-part DDR archive from the official Google Drive folder linked at github.com/nkicsl/DDR-dataset.

Integrity: each part's byte count must equal the server Content-Length; SHA-256 of every part is recorded in
data/raw/DDR/archive/SHA256SUMS (no publisher checksums exist); extraction (extract_ddr.py) verifies each member's
CRC-32 from the zip directory. Resumable. Licence: CC BY-NC-SA 4.0.
    .venv\\Scripts\\python src\\data\\download_ddr.py
"""
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/raw/DDR/archive"
FOLDER = "1z6tSFmxW_aNayUqVxx6h6bY4kwGzUTEC"
UA = {"User-Agent": "Mozilla/5.0"}
CHUNK = 8 << 20


def list_parts():
    html = urllib.request.urlopen(urllib.request.Request(f"https://drive.google.com/drive/folders/{FOLDER}", headers=UA), timeout=60).read().decode("utf-8", "replace")
    # Each file row carries data-id="<file id>" followed by its aria-label with the file name.
    parts = {}
    for m in re.finditer(r'data-id="([A-Za-z0-9_-]{20,})"', html):
        name = re.search(r"DDR-dataset\.zip\.\d{3}", html[m.start():m.start() + 4000])
        if name:
            parts.setdefault(name.group(0), m.group(1))
    if len(set(parts.values())) != len(parts):
        raise SystemExit("ambiguous Drive listing: one file id mapped to several part names")
    if len(parts) != 10:
        raise SystemExit(f"expected 10 parts in the Drive folder, found {sorted(parts)}")
    return dict(sorted(parts.items()))


def fetch(fid, dest):
    url = f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"
    have = dest.stat().st_size if dest.exists() else 0
    req = urllib.request.Request(url, headers={**UA, **({"Range": f"bytes={have}-"} if have else {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        if "text/html" in r.headers.get("Content-Type", ""):
            raise RuntimeError("Drive returned an HTML page (quota or confirmation), not file bytes")
        total = have + int(r.headers["Content-Length"])
        if have and r.status != 206:
            raise RuntimeError("server ignored the resume range")
        with open(dest, "ab" if have else "wb") as f:
            while block := r.read(CHUNK):
                f.write(block)
    return total


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parts = list_parts()
    (OUT.parent / "drive_parts.json").write_text(json.dumps(parts, indent=2))
    sums = []
    for name, fid in parts.items():
        dest = OUT / name
        for attempt in range(6):
            try:
                expected = fetch(fid, dest)
                break
            except Exception as exc:  # resume from the bytes already on disk
                print(f"{name}: attempt {attempt + 1} failed ({exc}); retrying", flush=True)
                time.sleep(20)
        else:
            sys.exit(f"{name}: download failed")
        size = dest.stat().st_size
        if size != expected:
            sys.exit(f"{name}: size {size} != Content-Length total {expected}")
        sums.append(f"{sha256(dest)}  {name}")
        print(f"{name}: {size} bytes OK", flush=True)
    (OUT / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    print("ALL PARTS DOWNLOADED", flush=True)


if __name__ == "__main__":
    main()
