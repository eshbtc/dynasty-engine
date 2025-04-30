import streamlit as st
import pandas as pd
import requests
import os
import json
import datetime

# --- Health endpoint using FastAPI ---
import threading
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

def run_health_api():
    uvicorn.run(app, host="0.0.0.0", port=8888, log_level="error")

threading.Thread(target=run_health_api, daemon=True).start()

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8008")

st.title("Dynasty Engine Dashboard")

# --- Fetch Trades from API ---
st.header("Trade History")
trades = pd.DataFrame()
try:
    resp = requests.get(f"{BACKEND_URL}/api/trades", timeout=10)
    if resp.ok:
        data = resp.json()
        trades = pd.DataFrame(data.get("trades", []))
        if not trades.empty:
            st.dataframe(trades)
        else:
            st.info("No trades found.")
    else:
        st.warning(f"Failed to fetch trades: {resp.status_code}")
except Exception as e:
    st.warning(f"Error fetching trades: {e}")

# --- Fetch Agent Decisions from API ---
st.header("Agent Decisions & Commentary")
decisions = pd.DataFrame()
try:
    resp = requests.get(f"{BACKEND_URL}/api/agent-decisions", timeout=10)
    if resp.ok:
        data = resp.json()
        decisions = pd.DataFrame(data.get("decisions", []))
        if not decisions.empty:
            st.dataframe(decisions)
        else:
            st.info("No agent decisions logged yet.")
    else:
        st.warning(f"Failed to fetch agent decisions: {resp.status_code}")
except Exception as e:
    st.warning(f"Error fetching agent decisions: {e}")

# Optional: Auto-refresh every 5 seconds for near real-time updates
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=5000, key="refresh")
except ImportError:
    pass  # streamlit-autorefresh not installed

# Show Basic Stats
if not trades.empty:
    total_trades = trades.shape[0]
    open_trades = trades[trades['outcome'] == 'OPEN'].shape[0] if 'outcome' in trades.columns else 0
    closed_trades = total_trades - open_trades
    st.metric("Total Trades", total_trades)
    st.metric("Open Trades", open_trades)
    st.metric("Closed Trades", closed_trades)

# Chat/Command Interface
st.header("Bot Command Center")
command = st.text_input("Send feedback or command to bot:")
if st.button("Submit Command"):
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/commands",
            json={"command": command},
            timeout=10
        )
        if resp.ok:
            st.success("Command recorded. Bot will adapt next cycle.")
        else:
            st.warning(f"Failed to submit command: {resp.status_code}")
    except Exception as e:
        st.warning(f"Error submitting command: {e}")