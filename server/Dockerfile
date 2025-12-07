FROM python:3.12-slim

# Install curl so we can install uv
RUN apt-get update && apt-get install -y curl ca-certificates && apt-get clean

# Install uv (no pip)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Copy requirements.txt
COPY requirements.txt .

# Install ALL Python deps using uv (not pip)
RUN uv pip install --system -r requirements.txt

# Copy server code
COPY . .

# Expose port from .env / compose
EXPOSE ${MCP_PORT:-8300}

CMD ["uvicorn", "server:app", "--reload", "--host", "0.0.0.0", "--port", "8300"]

