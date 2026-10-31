# Reproduce every reported number from saved predictions (no retraining). See tools/reproduce.py.
#   .\reproduce.ps1           verify, then regenerate results/KEY_NUMBERS.md and results/SCORECARD.md
#   .\reproduce.ps1 --check   verify only (exit 1 on any mismatch)
$root = $PSScriptRoot
$env:PYTHONPATH = Join-Path $root "src"
& (Join-Path $root ".venv\Scripts\python.exe") (Join-Path $root "tools\reproduce.py") @args
exit $LASTEXITCODE
