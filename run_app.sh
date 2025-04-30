#!/bin/bash
# Entrypoint script to run FastAPI backend and Streamlit dashboard
set -e

# Start FastAPI backend on port 8888 in the background
uvicorn api_status:app --host 0.0.0.0 --port 8888 &

# Start Streamlit dashboard on port 8080 in the foreground
exec streamlit run dashboard.py --server.port 8080
