@echo off
REM Pemasangan sekali jalan untuk Windows: venv Python, paket backend, paket & build frontend.
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo [!] Python belum terpasang. Pasang Python 3.10+ dari python.org & exit /b 1)
where npm >nul 2>nul || (echo [!] Node.js belum terpasang. Pasang Node.js 18+ dari nodejs.org & exit /b 1)

echo == Backend: membuat virtual environment ==
if not exist backend\.venv python -m venv backend\.venv
call backend\.venv\Scripts\python -m pip install --upgrade pip >nul
call backend\.venv\Scripts\pip install -r backend\requirements.txt || exit /b 1

echo == Frontend: memasang paket dan build ==
cd frontend
call npm install || exit /b 1
call npm run build || exit /b 1
cd ..
echo.
echo Selesai. Jalankan start.bat lalu buka http://localhost:8000
endlocal
