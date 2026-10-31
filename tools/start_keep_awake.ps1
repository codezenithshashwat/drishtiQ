# Start tools/keep_awake.py detached (same mechanism as start_queue.ps1); it exits when the queue does.
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "tools\keep_awake.py"
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = "`"$py`" `"$script`""; CurrentDirectory = $root }
"ReturnValue=$($r.ReturnValue) PID=$($r.ProcessId)"
