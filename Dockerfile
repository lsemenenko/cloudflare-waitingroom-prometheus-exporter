FROM python:3.11-slim

LABEL maintainer="Cloudflare Waiting Room Exporter"
LABEL description="Prometheus exporter for Cloudflare Waiting Room metrics"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./

# Create non-root user for security
RUN groupadd -r exporter && \
    useradd -r -g exporter -d /app -s /bin/false exporter && \
    chown -R exporter:exporter /app

USER exporter

# Expose metrics port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Set default environment variables
ENV POLL_INTERVAL=60
ENV HTTP_PORT=8000

# Run the exporter
CMD ["python", "waitingroom_exporter.py"]