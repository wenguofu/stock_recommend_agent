# ── 后端 ──
FROM python:3.11-slim AS backend

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 35000

CMD ["python3", "api_server.py"]


# ── 前端（开发用）──
FROM node:20-alpine AS frontend-dev

WORKDIR /app
COPY stock_frontend/package*.json ./
RUN npm ci

COPY stock_frontend/ .
EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
