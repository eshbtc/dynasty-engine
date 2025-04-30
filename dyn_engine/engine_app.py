"""Phase-2: unified async runtime / scheduler wrapper.

Usage (entry-point script):

    import asyncio
    from dyn_engine.engine_app import EngineApp

    app = EngineApp()
    asyncio.run(app.run())
"""
from __future__ import annotations

import asyncio
from typing import Callable, Awaitable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from ib_insync import IB

from settings import get_settings
from dyn_engine.logging_config import get_logger

logger = get_logger(__name__)


class EngineApp:
    def __init__(self) -> None:
        cfg = get_settings()
        self.scheduler = AsyncIOScheduler()
        self.tasks: list[asyncio.Task] = []
        self.ib = IB()
        self.cfg = cfg

    async def _connect_ib(self) -> None:
        if not self.ib.isConnected():
            await self.ib.connectAsync(
                self.cfg.ibkr_host, self.cfg.ibkr_port, clientId=self.cfg.ibkr_client_id
            )
            logger.info("Connected to IBKR host=%s port=%s", self.cfg.ibkr_host, self.cfg.ibkr_port)

    def schedule_cron(self, coro_func: Callable[..., Awaitable[None]], minutes: int) -> None:
        """Schedule coroutine every `minutes`."""
        self.scheduler.add_job(coro_func, "interval", minutes=minutes)

    async def run(self) -> None:
        logger.info("Starting EngineApp runtime")
        await self._connect_ib()

        # Import here to avoid circulars
        from dynasty_engine import dynasty_engine_cycle, evaluate_assets, evaluate_hedges, set_ib  # type: ignore
        from dyn_engine.execution import get_execution_service

        # Inject shared IB into dynasty_engine module & preload execution service
        set_ib(self.ib)
        get_execution_service(self.ib)  # initialise singleton

        # schedule
        self.schedule_cron(dynasty_engine_cycle, 30)
        self.schedule_cron(evaluate_assets, 60)
        self.schedule_cron(evaluate_hedges, 240)

        # start scheduler
        self.scheduler.start()
        logger.info("Scheduler started")

        try:
            while True:
                await asyncio.sleep(3600)  # keep loop alive
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Shutdown signal received")
        finally:
            self.scheduler.shutdown(wait=False)
            await self._disconnect_ib()
            logger.info("EngineApp stopped")

    async def _disconnect_ib(self) -> None:
        if self.ib.isConnected():
            self.ib.disconnect()
