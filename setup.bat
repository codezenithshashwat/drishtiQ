@echo off
rem RetinaScreen: one-time setup on a new laptop (creates .venv and installs the packages).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
pause
