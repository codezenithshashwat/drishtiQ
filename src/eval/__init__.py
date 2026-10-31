"""Evaluation harness. Run from the project root with src on the path:

    .venv\\Scripts\\python -m eval make-splits
    .venv\\Scripts\\python -m eval grade --model v0
    .venv\\Scripts\\python -m eval segment --model v0

Every run appends one row to results/registry.csv and writes details to results/runs/<run_id>/.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
