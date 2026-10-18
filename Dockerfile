# Portfolio Analyzer: React front end + FastAPI backend in one image (used by Render).
# The data is the prebuilt DuckDB file in data/; nothing is downloaded at run time.

# ---- front end
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- backend
FROM python:3.10-slim
WORKDIR /app
COPY backend/requirements-deploy.txt backend/
RUN pip install --no-cache-dir -r backend/requirements-deploy.txt
COPY backend/ backend/
# Editable install so smallcap.config.ROOT resolves to /app (data/ and frontend/dist live there).
# yfinance (the "real" extra) is deliberately not installed: the app cannot fetch market data.
RUN pip install --no-cache-dir --no-deps -e backend
COPY data/smallcap.duckdb data/real_report.json data/
COPY data/cache/backtests/ data/cache/backtests/
COPY --from=web /app/frontend/dist frontend/dist

WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "uvicorn smallcap.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
