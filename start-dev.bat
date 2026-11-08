@echo off
REM Mode pengembangan: backend auto-reload (:8000) + frontend Vite hot reload (:5173)
cd /d "%~dp0"
start "PasporKebun API" cmd /k "cd backend && .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000"
cd frontend
start "" http://localhost:5173
npm run dev
