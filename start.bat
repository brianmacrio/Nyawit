@echo off
REM Menjalankan PasporKebun (backend menyajikan frontend hasil build) di http://localhost:8000
cd /d "%~dp0backend"
if not exist .venv (echo Jalankan setup.bat terlebih dahulu & exit /b 1)
start "" http://localhost:8000
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
