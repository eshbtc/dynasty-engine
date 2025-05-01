# Dockerfile

# ---- Builder Stage ----
FROM python:3.11-slim AS builder
WORKDIR /app

# Install dependencies
COPY requirements.txt .
# Using --no-cache-dir here is fine as this layer is cached
RUN pip install --no-cache-dir -r requirements.txt

# ---- Final Stage ----
FROM python:3.11-slim
WORKDIR /app

# Copy installed dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application code
COPY . .

# Run Flask API (with Prometheus metrics) on the port specified by Cloud Run
# Note: EXPOSE is documentation; Cloud Run uses the PORT env var directly.
# EXPOSE 8080
CMD exec gunicorn --bind 0.0.0.0:${PORT:-8080} -w 1 -k uvicorn.workers.UvicornWorker api_status:app
