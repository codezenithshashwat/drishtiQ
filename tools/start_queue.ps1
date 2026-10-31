# Start the GPU queue as a detached process that outlives the shell and the tooling session.
# Win32_Process.Create (via CIM) parents the process to the WMI provider host, not to this shell's process tree or job,
# and gives it no visible console. (The venv's pythonw.exe launcher exits silently when started this way; python.exe works.)
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "tools\gpu_queue.py"
$out = Join-Path $root "queue\logs\queue_stdout.log"
New-Item -ItemType Directory -Force (Join-Path $root "queue\logs") | Out-Null
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = "cmd /c `"`"$py`" `"$script`" >> `"$out`" 2>&1`""; CurrentDirectory = $root }
"ReturnValue=$($r.ReturnValue) PID=$($r.ProcessId) (cmd wrapper; the queue PID is in queue\queue.pid)"

# Block system sleep while the queue runs (a sleeping laptop froze the queue for 9 h on 2026-10-29).
& (Join-Path $PSScriptRoot "start_keep_awake.ps1")
