@echo off
REM Start Hydra from source without a console window (after the one-time setup in README.md)
cd /d "%~dp0"
if exist .venv\Scripts\pythonw.exe (
  start "" ".venv\Scripts\pythonw.exe" main.py
) else (
  start "" pythonw main.py
)
