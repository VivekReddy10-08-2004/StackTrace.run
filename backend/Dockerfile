# ── StackTrace.run backend ─────────────────────────────────────────────
# Pinned to Python 3.12 so every dependency has a prebuilt wheel.
# Compatible with both local Docker Compose and Hugging Face Spaces.
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

# Expose 7860 to match Hugging Face's natural ingress default
EXPOSE 7860

# Updated liveness probe targetting the new internal container port
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:7860/api/health').status==200 else sys.exit(1)"

# Run Waitress on port 7860.
CMD ["waitress-serve", "--host=0.0.0.0", "--port=7860", "app:app"]