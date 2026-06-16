# ARIA — HuggingFace Spaces Dockerfile
# HF Spaces runs containers as a non-root user (uid 1000).
# All caches must live in /app so they're accessible at runtime.

FROM python:3.11-slim

# Stream logs immediately (no buffering)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Point ALL model caches to /app/.cache so they survive the user switch
ENV HF_HOME=/app/.cache
ENV TRANSFORMERS_CACHE=/app/.cache
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache

WORKDIR /app

# System deps — build-essential needed for some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model into /app/.cache so first request is instant
# (runs as root during build, but /app/.cache is world-readable)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" \
    && chmod -R 777 /app/.cache

# Copy source
COPY . .

# HuggingFace Spaces expects port 7860
EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
