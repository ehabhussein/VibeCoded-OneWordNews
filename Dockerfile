FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY static/ ./static/
COPY templates/ ./templates/

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Expose port for web UI
EXPOSE 8080

# Run the application
CMD ["python", "-u", "src/main.py"]
