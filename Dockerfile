# ── Hugging Face Space image (Docker SDK) ──────────────────────────────
# HF Spaces builds from a Dockerfile at the repo ROOT and serves `app_port`
# (7860, from the README frontmatter). This image runs the Flask backend API.
# Build context is the repo root, so paths are prefixed with backend/.
#
# (The backend/Dockerfile is the equivalent image for local docker-compose.)
# ────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

# Dependencies first (layer caching).
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend source only (the frontend is hosted separately).
COPY backend/ .

# Non-root user.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:7860/api/health').status==200 else sys.exit(1)"

# Production WSGI server on HF's ingress port.
CMD ["waitress-serve", "--host=0.0.0.0", "--port=7860", "app:app"]
