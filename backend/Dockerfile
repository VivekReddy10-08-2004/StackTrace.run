# ── StackTrace.run backend ─────────────────────────────────────────────
# Pinned to Python 3.12 so every dependency has a prebuilt wheel (the Turso
# drivers have no wheels on 3.14). Build context is the backend/ directory.
#
#   docker build -t stacktrace-backend ./backend
#   docker run --rm -p 8000:8000 --env-file ./backend/.env stacktrace-backend
# ────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

# Install dependencies first so this layer is cached across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application source.
COPY . .

# Run as a non-root user.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Liveness probe against the health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else sys.exit(1)"

# Production WSGI server (not Flask's dev server). Serves the `app` object in app.py.
CMD ["waitress-serve", "--host=0.0.0.0", "--port=8000", "app:app"]
