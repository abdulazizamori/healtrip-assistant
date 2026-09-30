# Single-service image for hosting (Render): the API serves the statically exported frontend on the same origin.
# Local development uses docker-compose.yml (separate db / api / web containers) instead.

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# empty API URL = same origin
ENV STATIC_EXPORT=1 NEXT_PUBLIC_API_URL= NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY db ./db
COPY --from=web /web/out ./static
RUN useradd --create-home appuser
USER appuser
# Render sets PORT; --proxy-headers so rate limiting sees the client IP, not the load balancer's
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
