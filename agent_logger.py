# agent_logger.py
# Centralized logging for RL agent decisions, observations, commentary, and errors
import os
import pandas as pd
from datetime import datetime
from threading import Lock

LOG_PATH = os.path.join("data", "agent_decisions.csv")
LOG_LOCK = Lock()

def log_agent_decision(symbol, obs_vec, rl_action, commentary, error=None):
    row = {
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": symbol,
        "obs_vec": repr(obs_vec.tolist()) if hasattr(obs_vec, 'tolist') else str(obs_vec),
        "action": rl_action,
        "commentary": commentary,
        "error": error or ""
    }
    df = pd.DataFrame([row])
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with LOG_LOCK:
        header = not os.path.exists(LOG_PATH)
        df.to_csv(LOG_PATH, mode='a', header=header, index=False)
