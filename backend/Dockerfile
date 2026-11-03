# syntax=docker/dockerfile:1
# ArchitectIQ - Backend Containerfile
# Base runtime: Python 3.11 Slim (matching production runtime 3.11.9)
FROM python:3.11-slim AS runtime

# Set environment variable
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    ENVIRONMENT=production \
    PYTHONPATH=/app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and group for security
RUN groupadd -r -g 10001 appgroup && \
    useradd -r -u 10001 -g appgroup -s /sbin/nologin -d /app appuser

WORKDIR /app

# Install Python production dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy backend application source and test configuration
COPY backend /app/backend
COPY pytest.ini /app/pytest.ini

# Set ownership to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER 10001:10001

# Expose backend service port
EXPOSE 8000

# Container healthcheck targeting the production health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production application entrypoint using Uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
