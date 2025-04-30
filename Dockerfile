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

# Run Streamlit on the port specified by Cloud Run
# Note: EXPOSE is documentation; Cloud Run uses the PORT env var directly.
# EXPOSE 8080 # Or whatever PORT is set to
# Start both Streamlit and healthcheck server for Cloud Run compatibility
CMD bash -c "streamlit run dashboard.py --server.port=${PORT:-8080} & python healthcheck.py"
