"""Centralised settings using Pydantic BaseSettings.

Read precedence:
1. environment variables
2. .env file (if present)
3. config.yaml (legacy – will be deprecated in Phase 1)
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseSettings, Field
from dotenv import load_dotenv
import yaml

# Load .env file if present (does nothing otherwise)
load_dotenv()

ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # --- API / Keys ---
    openai_api_key: str | None = Field(None, env="OPENAI_API_KEY")
    polygon_key: str | None = Field(None, env="POLYGON_KEY")
    tradier_key: str | None = Field(None, env="TRADIER_KEY")

    # --- Slack / Notifications ---
    slack_webhook_url: str | None = Field(None, env="SLACK_WEBHOOK_URL")

    # --- IBKR ---
    ibkr_username: str | None = Field(None, env="IBKR_USERNAME")
    ibkr_password: str | None = Field(None, env="IBKR_PASSWORD")
    ibkr_host: str = Field("127.0.0.1", env="IBKR_HOST")
    ibkr_port: int = Field(7497, env="IBKR_PORT")
    ibkr_client_id: int = Field(1, env="IBKR_CLIENT_ID")

    # --- Engine ---
    dynasty_halt: bool = Field(False, env="DYNASTY_HALT")
    paper_trade: bool = Field(False, env="PAPER_TRADE")  # if true, skip live orders
    prom_port: int = Field(9000, env="PROM_PORT")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    trade_db_path: str = Field("trade_tracker.db", env="TRADE_DB_PATH")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor. Also merges any legacy config.yaml key overrides."""
    s = Settings()

    cfg_path = ROOT / "config.yaml"
    if cfg_path.exists():
        with cfg_path.open("r") as f:
            legacy = yaml.safe_load(f) or {}
            # Simple shallow merge – later we will migrate fully to settings
            for key, value in legacy.items():
                # Only fill attributes that are still None / default
                if hasattr(s, key) and getattr(s, key) in (None, ""):
                    setattr(s, key, value)
    return s
