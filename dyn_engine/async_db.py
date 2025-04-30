"""Asynchronous DB helper using aiosqlite (Phase-1).

This module provides a lazily-initialised singleton `AsyncDB` instance. Import and
`await get_db()` from any coroutine to get the connection:

    from dyn_engine.async_db import get_db

    async def save(trade):
        db = await get_db()
        await db.save_trade(trade)

It recreates the schema if missing and runs with WAL mode for concurrency.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import aiosqlite

from settings import get_settings
from dyn_engine.logging_config import get_logger

logger = get_logger(__name__)


class AsyncDB:
    """Lightweight wrapper around aiosqlite connection."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._conn is not None:
            return
        self._conn = await aiosqlite.connect(self._path)
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._create_tables()
        logger.info("AsyncDB connected to %s", self._path)

    async def _create_tables(self) -> None:
        if self._conn is None:
            raise RuntimeError("DB not connected")
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                ticker TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                strategy_price REAL,
                avg_fill_price REAL,
                commission REAL,
                slippage_bp REAL,
                status TEXT
            )
            """
        )
        await self._conn.commit()

    async def save_trade(self, trade: Dict[str, Any]) -> bool:
        """Persist a trade dict; returns True on success."""
        if self._conn is None:
            await self.connect()
        if not trade or "ticker" not in trade:
            logger.warning("Invalid trade data: %s", trade)
            return False
        sql = (
            "INSERT INTO trades (timestamp, ticker, action, quantity, strategy_price, "
            "avg_fill_price, commission, slippage_bp, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        ts = _dt.datetime.now().isoformat()
        params = (
            ts,
            trade.get("ticker"),
            trade.get("action"),
            trade.get("quantity"),
            trade.get("strategy_price"),
            trade.get("avg_fill_price"),
            trade.get("commission"),
            trade.get("slippage_bp"),
            trade.get("status", "Unknown"),
        )
        try:
            async with self._lock:
                await self._conn.execute(sql, params)
                await self._conn.commit()
            logger.debug("Saved trade %s", trade)
            return True
        except Exception as e:
            logger.exception("Failed to save trade: %s", e)
            return False

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            logger.info("AsyncDB connection closed")
            self._conn = None


# ---- Singleton helpers ----
_db_instance: Optional[AsyncDB] = None
_db_lock = asyncio.Lock()


async def get_db() -> AsyncDB:
    """Return a lazily-initialised singleton DB instance."""
    global _db_instance
    if _db_instance is None:
        async with _db_lock:
            if _db_instance is None:
                cfg = get_settings()
                _db_instance = AsyncDB(cfg.trade_db_path)
                await _db_instance.connect()
    return _db_instance


async def close_db() -> None:
    global _db_instance
    if _db_instance is not None:
        await _db_instance.close()
        _db_instance = None
