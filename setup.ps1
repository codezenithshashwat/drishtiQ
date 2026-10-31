# RetinaScreen: one-time setup on a new Windows laptop (setup.bat calls this).
# Creates the Python environment in .venv with the exact package versions of the development laptop, then runs preflight.
# Needs Python 3.11 and an internet connection (about 3 GB of packages, mostly PyTorch). Node.js and Git are not needed.
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
Set-Location $root

function Find-Python311 {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $exe = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { return "$exe".Trim() }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $ver = & python -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ("$ver".Trim() -eq "3.11") { return (Get-Command python).Source }
    }
    return $null
}

$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    $py = Find-Python311
    if (-not $py) {
        Write-Host "Python 3.11 not found. Install Python 3.11 (64-bit) from https://www.python.org/downloads/windows/," -ForegroundColor Red
        Write-Host "tick 'Add python.exe to PATH' in the installer, then run setup.bat again." -ForegroundColor Red
        exit 1
    }
    Write-Host "Creating the Python environment in .venv with $py ..."
    & $py -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Host "Could not create .venv." -ForegroundColor Red; exit 1 }
}

Write-Host "Installing packages (exact versions from requirements-lock.txt; this takes a while) ..."
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r requirements-lock.txt --extra-index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { Write-Host "Package installation failed; see the messages above." -ForegroundColor Red; exit 1 }

Write-Host "`nChecking the installation ..." -ForegroundColor Cyan
& $venvPy preflight.py
if ($LASTEXITCODE -ne 0) { Write-Host "Preflight reported a FAIL; see SETUP_NEW_LAPTOP.md, Troubleshooting." -ForegroundColor Red; exit 1 }
Write-Host "`nSetup complete. Start the app with start.bat." -ForegroundColor Green
