# PasporKebun: satu container (FastAPI menyajikan frontend hasil build).
# Build:  docker build -t pasporkebun .
# Jalan:  docker run -p 8000:8000 -e PK_SECRET_KEY=ganti-dengan-acak pasporkebun

# --- tahap 1: build frontend (React + Vite) ---
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- tahap 2: backend Python (CPU saja, tanpa GPU) ---
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PK_DATA_DIR=/app/backend/data
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
COPY --from=web /web/dist /app/frontend/dist
# jalankan sebagai pengguna biasa, bukan root
RUN useradd --create-home app && mkdir -p /app/backend/data && chown -R app /app/backend/data
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\",\"8000\")}/api/health')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
