FROM python:3.11-slim

# Create non-root user
RUN useradd -ms /bin/bash appuser
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
	gcc libc6-dev \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Directories
RUN mkdir -p /app/data /app/work /app/logs && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "src.main", "--help"]