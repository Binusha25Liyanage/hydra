@echo off
REM Start Hydra from source (after the one-time setup in README.md)
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
python main.py
