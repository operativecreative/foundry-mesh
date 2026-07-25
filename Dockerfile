FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" \
    aiosqlite

# Copy source
COPY benchmarks/ ./benchmarks/
COPY mesh/ ./mesh/
COPY tests/ ./tests/
COPY Makefile .

# Create data directory
RUN mkdir -p /app/data

# Default: run validation
CMD ["make", "validate"]
