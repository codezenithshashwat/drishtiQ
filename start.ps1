# RetinaScreen: one-click local start (start.bat calls this).
#   .\start.ps1             check, (re)build the page if needed, start the app on http://localhost:8000 and open it
#   .\start.ps1 -Restart    also stop an older RetinaScreen backend that is still holding port 8000
param([switch]$Restart, [int]$Port = 8000)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "Python environment not found at .venv. See README: Run it locally, step 1." -ForegroundColor Red; exit 1 }

function Get-BackendCommit {
    try { (Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/version" -TimeoutSec 3).commit } catch { $null }
}

# Commit of the code on disk; a copy without git history (project zip) uses the stamp in BUILD_COMMIT.
$head = $null
if (Get-Command git -ErrorAction SilentlyContinue) { $head = cmd /c "git rev-parse --short HEAD 2>nul" }
if (-not $head -and (Test-Path (Join-Path $root "BUILD_COMMIT"))) { $head = Get-Content (Join-Path $root "BUILD_COMMIT") -TotalCount 1 }
$head = "$head".Trim()
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    $running = Get-BackendCommit
    if ($running -eq $head) {
        Write-Host "RetinaScreen ($head) is already running; opening it." -ForegroundColor Green
        Start-Process "http://localhost:$Port"; exit 0
    }
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($busy[0].OwningProcess)"
    if ($Restart -and $owner.CommandLine -match "backend\.app") {
        Write-Host "Stopping the older RetinaScreen backend (running $running, code is $head)."
        Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "uvicorn backend\.app:app" -and $_.CommandLine -match "--port $Port" } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        Start-Sleep -Seconds 2
    } else {
        Write-Host "Port $Port is in use by $($owner.Name) (commit $running). Close it, or run: start.bat -Restart" -ForegroundColor Red; exit 1
    }
}

$build = Join-Path $root "frontend\dist\build-info.json"
$built = if (Test-Path $build) { (Get-Content $build -Raw | ConvertFrom-Json).commit } else { $null }
if ($built -ne $head) {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Write-Host "Rebuilding the page (built from $built, code at $head)..."
        Push-Location (Join-Path $root "frontend")
        try {
            & npm.cmd run build | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Frontend build failed. See the build errors above." }
        } finally { Pop-Location }
    } else {
        Write-Host "The page was built from $built but the code is at $head, and npm is not installed to rebuild it." -ForegroundColor Yellow
    }
}

& $py preflight.py --port $Port
if ($LASTEXITCODE -ne 0) { Write-Host "Preflight failed; fix the FAIL items above (README: Troubleshooting)." -ForegroundColor Red; exit 1 }

$env:PYTHONPATH = Join-Path $root "src"
$env:HF_HUB_OFFLINE = "1"
Write-Host "`nStarting RetinaScreen on http://localhost:$Port (close this window to stop it)..." -ForegroundColor Cyan
# Open the browser once the models have loaded.
Start-Job -ArgumentList $Port -ScriptBlock {
    param($p)
    for ($i = 0; $i -lt 300; $i++) {
        try { if ((Invoke-RestMethod "http://127.0.0.1:$p/api/health" -TimeoutSec 2).status -eq "ok") { Start-Process "http://localhost:$p"; return } } catch {}
        Start-Sleep -Seconds 1
    }
} | Out-Null
& $py -m uvicorn backend.app:app --host 127.0.0.1 --port $Port --app-dir $root
