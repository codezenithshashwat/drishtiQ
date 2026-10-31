@echo off
rem RetinaScreen: one-click local start. Arguments are passed on (e.g. start.bat -Restart).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 pause
