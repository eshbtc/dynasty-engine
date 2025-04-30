# Streamlit Cloud Run Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements-streamlit.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose Cloud Run port
ENV PORT=8080
EXPOSE 8080

# Optional: Backend API URL (set at deploy time)
ENV BACKEND_URL=https://dynasty-engine-594497653266.us-central1.run.app

# Set health check to correct port for watchdog
ENV DYNASTY_HEALTH_URL=http://localhost:8888/health

# Run Streamlit on Cloud Run's port
CMD streamlit run dashboard.py --server.port $PORT --server.address 0.0.0.0 --server.enableXsrfProtection false --server.enableCORS true
