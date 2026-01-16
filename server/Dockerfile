FROM python:3.12-slim

# Install system dependencies for PostgreSQL and health checks
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    postgresql-client \
    netcat-openbsd \
    procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv (no pip)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Copy requirements.txt first for better caching
COPY requirements.txt .

# Install ALL Python deps using uv (not pip)
RUN uv pip install --system -r requirements.txt

# Install additional async dependencies
RUN uv pip install --system asyncpg uvloop

# Copy server code
COPY . .

# Create health check script
RUN echo '#!/bin/bash\n\
echo "[$(date)] Health check starting..."\n\
if curl -f http://localhost:8300/health > /dev/null 2>&1; then\n\
  echo "[$(date)] Health check: MCP server is healthy"\n\
  exit 0\n\
else\n\
  echo "[$(date)] Health check: MCP server is unhealthy"\n\
  exit 1\n\
fi' > /usr/local/bin/health-check.sh && chmod +x /usr/local/bin/health-check.sh

# Expose port
EXPOSE ${MCP_PORT:-8300}

# Use uvloop for better async performance
ENV PYTHONPATH=/app
ENV UVLOOP_ENABLED=1

# Start script that handles both development and production
CMD ["python", "-c", "import os; import uvicorn; uvicorn.run('server:app', host='0.0.0.0', port=int(os.getenv('MCP_PORT', '8300')), reload=os.getenv('UVICORN_RELOAD', 'false').lower() == 'true', log_level=os.getenv('LOG_LEVEL', 'info').lower())"]


