# One image = the whole app: the dashboard is built once, FastAPI serves it.

# ---- 1. build the dashboard ----
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. run the backend (+ the built dashboard) ----
FROM python:3.13-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY demo/ ./demo/
COPY benchmark/results/ ./benchmark/results/
COPY --from=web /web/dist ./frontend/dist
WORKDIR /app/backend
# $PORT is set by Render/Railway/Fly; 8000 when you run it yourself.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
