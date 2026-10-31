"""Pre-push scan over the whole git history: large blobs, secrets, attribution lines, image/weight files, authors.

    .venv\\Scripts\\python tools\\history_scan.py

Prints a report and exits 1 if anything needs attention. Reads git objects only; changes nothing.
"""
import re
import subprocess
import sys

LIMIT = 50 * 2**20
SECRET = re.compile(rb"(hf_[A-Za-z0-9]{30,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{32,}|"
                    rb"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----|\"key\"\s*:\s*\"[0-9a-f]{32}\")")
# Built from parts so this file does not match its own search.
ATTRIBUTION = re.compile("|".join(["co-" + "authored-by", "gener" + "ated with", "cla" + "ude", "anth" + "ropic"]), re.I)
BINARY_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".pt", ".pth", ".ckpt", ".onnx", ".safetensors", ".npy", ".npz", ".zip")


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def main():
    problems = []
    objects = git("rev-list", "--objects", "--all").decode(errors="replace").splitlines()
    paths = {}
    for line in objects:
        sha, _, path = line.partition(" ")
        if path:
            paths[sha] = path
    batch = subprocess.run(["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
                           input="\n".join(paths).encode(), capture_output=True, check=True).stdout.decode().splitlines()
    blobs = [(s, int(n)) for s, t, n in (l.split() for l in batch) if t == "blob"]
    big = [(paths[s], n) for s, n in blobs if n > LIMIT]
    print(f"Blobs in history: {len(blobs)}; largest {max(n for _, n in blobs) / 2**20:.1f} MB")
    print(f"[{'FAIL' if big else 'PASS'}] blobs over 50 MB: {big or 'none'}")
    problems += big

    hits = []
    for s, n in blobs:
        if n > 20 * 2**20:
            continue
        data = git("cat-file", "-p", s)
        if SECRET.search(data):
            hits.append(paths[s])
    print(f"[{'FAIL' if hits else 'PASS'}] secret patterns (HF/GitHub/AWS/OpenAI tokens, private keys, API-key JSON): {sorted(set(hits)) or 'none'}")
    problems += hits

    images = sorted({p for p in paths.values() if p.lower().endswith(BINARY_EXT)})
    print(f"[{'WARN' if images else 'PASS'}] image/weight/archive files ever committed: {images or 'none'}")

    log = git("log", "--all", "--format=%H%x1f%an <%ae>%x1f%cn <%ce>%x1f%B%x1e").decode(errors="replace")
    authors, flagged = set(), []
    for entry in filter(None, (e.strip() for e in log.split("\x1e"))):
        h, a, c, body = entry.split("\x1f", 3)
        authors |= {a, c}
        if ATTRIBUTION.search(body):
            flagged.append(f"{h[:7]}: {next(l for l in body.splitlines() if ATTRIBUTION.search(l)).strip()[:100]}")
    print(f"[INFO] authors/committers: {sorted(authors)}")
    print(f"[{'FAIL' if flagged else 'PASS'}] attribution lines in commit messages: {flagged or 'none'}")
    problems += flagged
    if len(authors) != 1:
        print("[WARN] more than one author/committer identity")
    print("\nRESULT:", "needs attention" if problems else "clean")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
