
# ---- Base image ----
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps (slim image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl tini && \
    rm -rf /var/lib/apt/lists/*

# Workdir
WORKDIR /app

# Copy only requirements first for better caching
COPY requirements.txt /app/requirements.txt

# Install Python deps
RUN pip install --upgrade pip && \
    pip install -r /app/requirements.txt

# Create a non-root user
RUN useradd -ms /bin/bash appuser
USER appuser

# Copy app source
COPY --chown=appuser:appuser app /app/app

# Expose port
EXPOSE 8000

# Healthcheck (simple GET /health)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request, sys \
try: \
    with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as r: \
        sys.exit(0 if r.status == 200 else 1) \
except Exception: \
    sys.exit(1)"

# Use tini as PID 1 for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command (no --reload inside container by default)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
