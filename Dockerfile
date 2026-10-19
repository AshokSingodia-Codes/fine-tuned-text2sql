# Build Stage 1: Build React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Build Stage 2: Python Serving Backend
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (UID 1000 for Hugging Face Spaces compatibility)
RUN useradd -m -u 1000 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir huggingface_hub

# Copy application code
COPY src/ src/
COPY configs/ configs/
COPY config/ config/
COPY db/ db/
COPY NOTICE .
COPY README.md .

# Copy compiled frontend into directory served by FastAPI
COPY --from=frontend-builder /build/dist frontend/dist

# Set permissions for non-root execution
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 7860 8000

ENV APP_PROFILE=demo
ENV PORT=7860
ENV HOST=0.0.0.0
ENV MODEL_BACKEND=mock

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:7860/health || exit 1

CMD ["sh", "-c", "uvicorn src.t2s.serving.app:app --host 0.0.0.0 --port ${PORT:-7860}"]
