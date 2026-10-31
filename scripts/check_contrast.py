"""WCAG 2.1 contrast check for the colour pairs declared in design/tokens.json.
    .venv\\Scripts\\python scripts\\check_contrast.py      (exit code 1 if any pair fails)
"""
import json
import sys
from pathlib import Path

TOKENS = json.loads((Path(__file__).resolve().parents[1] / "design/tokens.json").read_text(encoding="utf-8"))


def resolve(path):
    cur = TOKENS
    for part in path.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def luminance(hex_colour):
    rgb = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def main():
    failures = 0
    for fg, bg, minimum in TOKENS["contrast"]["pairs"]:
        r = ratio(resolve(fg), resolve(bg))
        ok = r >= minimum
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {r:5.2f} (min {minimum})  {fg} on {bg}")
    print(f"\n{len(TOKENS['contrast']['pairs']) - failures}/{len(TOKENS['contrast']['pairs'])} pairs pass")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
