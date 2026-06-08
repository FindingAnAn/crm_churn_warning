# Stage 1: Build dependencies
FROM python:3.11-slim-bookworm AS builder

# Set environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# System dependencies for building Python packages (psycopg2, scikit-learn etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Stage 2: Runtime Environment
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/appuser/.local/bin:$PATH" \
    PYTHONPATH="/app/src"

# Install runtime system dependencies (required for psycopg2-binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (Rule 5.4)
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --create-home appuser

WORKDIR /app

# Copy built dependencies from builder stage
COPY --from=builder --chown=appuser:appgroup /root/.local /home/appuser/.local

# Copy application source code
COPY --chown=appuser:appgroup src/ ./src/

# Ensure logs directory exists and appuser has permissions for /app
RUN mkdir -p /app/logs && chown -R appuser:appgroup /app

USER appuser

# Healthcheck for standalone process (Rule 4.1 - Observable Orchestration)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import psycopg2" || exit 1

ENTRYPOINT ["python", "-m"]
CMD ["src.scripts.check_db_status"]
