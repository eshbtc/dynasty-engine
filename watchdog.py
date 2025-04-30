# ------------------------------------------------------------------------------
# 9️⃣  WATCHDOG  (watchdog.py – optional Cloud Run side‑car)
# ------------------------------------------------------------------------------
import time
import requests
import os
import sys

# Default to Streamlit health endpoint if DYNASTY_HEALTH_URL is not set
HEALTH_ENDPOINT = os.getenv('DYNASTY_HEALTH_URL','http://localhost:8501/_stcore/health')
CHECK_INTERVAL_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 4

print(f"Watchdog started. Monitoring endpoint: {HEALTH_ENDPOINT}")

while True:
    try:
        print(f"Checking health endpoint: {HEALTH_ENDPOINT}...")
        r = requests.get(HEALTH_ENDPOINT, timeout=REQUEST_TIMEOUT_SECONDS)
        r.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        print(f"Health check successful (Status: {r.status_code}).")

    except requests.exceptions.Timeout:
        print(f'Watchdog: Health check timed out after {REQUEST_TIMEOUT_SECONDS} seconds. Exiting for restart.')
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f'Watchdog: Health check failed ({e}). Exiting for restart.')
        sys.exit(1)
    except Exception as e:
        # Catch any other unexpected errors during the check
        print(f'Watchdog: An unexpected error occurred ({e}). Exiting for restart.')
        sys.exit(1)

    # Wait before the next check
    time.sleep(CHECK_INTERVAL_SECONDS)
