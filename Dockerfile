# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Copy lockfile & install runtime deps globally (no venv)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Runtime env
ENV PORT=8000 \
    FX_API_BASE=https://api.frankfurter.dev/v1 \
    HTTP_TIMEOUT=6.0 \
    CACHE_TTL_SECONDS=30

EXPOSE 8000

# Healthcheck (Streamable HTTP lives at /mcp)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["sh", "-c", "curl -fsS http://127.0.0.1:${PORT:-8000}/mcp >/dev/null || exit 1"]

# Non-root user (optional; safe with system site-packages)
RUN useradd -u 10001 -m appuser && chown -R appuser:appuser /app
USER appuser

# Start server (use system Python, not uv)
CMD ["python", "-m", "app.main"]
