"""Download the MMRDR figshare archive (v2) with resume and MD5 verification.

Source: https://doi.org/10.6084/m9.figshare.29423747.v2 (CC BY 4.0).
Files land in data/raw/MMRDR/archive/ and are never modified after verification.
"""
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "MMRDR" / "archive"
API = "https://api.figshare.com/v2/articles/29423747/files"
CHUNK = 8 * 1024 * 1024


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def fetch(url, dest, size):
    have = dest.stat().st_size if dest.exists() else 0
    if have == size:
        return
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "ab" if have else "wb") as f:
        while block := r.read(CHUNK):
            f.write(block)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = json.load(urllib.request.urlopen(API, timeout=60))
    (OUT.parent / "figshare_files.json").write_text(json.dumps(files, indent=2))
    for meta in sorted(files, key=lambda m: m["name"]):
        dest = OUT / meta["name"]
        for attempt in range(5):
            try:
                fetch(meta["download_url"], dest, meta["size"])
                break
            except Exception as exc:  # network hiccup: resume from current size
                print(f"{meta['name']}: attempt {attempt + 1} failed ({exc}); retrying", flush=True)
                time.sleep(10)
        ok = dest.stat().st_size == meta["size"] and md5(dest) == meta["computed_md5"]
        print(f"{meta['name']}: {'OK' if ok else 'MISMATCH'}", flush=True)
        if not ok:
            sys.exit(f"verification failed for {meta['name']}")
    print("ALL PARTS VERIFIED", flush=True)


if __name__ == "__main__":
    main()
