"""Risk management utilities (Phase-3).

Tracks max equity, calculates drawdown, checks manual halt flag.
"""
from __future__ import annotations

from typing import Tuple
from dyn_engine.logging_config import get_logger
from settings import get_settings

logger = get_logger(__name__)


import os

class RiskManager:
    def __init__(self) -> None:
        self._risk_log_path = os.path.join(os.path.dirname(__file__), '../risk_events.log')

        cfg = get_settings()
        self.drawdown_limit_pct: float = 5.0  # configurable later
        self.max_equity: float = 0.0
        self.cfg = cfg
        # --- Option exposure limits ---
        # Gross portfolio greek caps (can be overridden via env or config later)
        self.delta_limit: float = 10_000.0  # dollar-delta (shares equiv)
        self.vega_limit: float = 50_000.0   # vega per 1 vol pt

        self.net_delta: float = 0.0
        self.net_vega: float = 0.0

    # ---------------------------------------------------------------------
    # Greeks
    # ---------------------------------------------------------------------

    def add_greek_exposure(self, delta_change: float = 0.0, vega_change: float = 0.0) -> bool:
        """Accumulate greek exposures and check against caps.

        Parameters
        ----------
        delta_change : float
            Signed delta exposure to add (negative for short delta).
        vega_change : float
            Signed vega exposure to add (negative for short vega).

        Returns
        -------
        bool
            True if exposure exceeds limits **after** applying change (halt).
        """
        self.net_delta += delta_change
        self.net_vega += vega_change

        over_delta = abs(self.net_delta) > self.delta_limit
        over_vega = abs(self.net_vega) > self.vega_limit

        if (over_delta or over_vega) and not getattr(self, "_greek_alerted", False):
            msg = (
                f"🚨 Greek limits breached – Δ={self.net_delta:.0f}/{self.delta_limit}, "
                f"Vega={self.net_vega:.0f}/{self.vega_limit}"
            )
            try:
                from metrics_exporter import send_push, ensure_exporter
                ensure_exporter()
                send_push(msg)
            except Exception as exc:
                logger.error("RiskManager greek push error: %s", exc)
            logger.warning(msg)
            self._log_risk_event(msg)
            self._greek_alerted = True

        return over_delta or over_vega

    def update_and_check(self, current_equity: float) -> Tuple[bool, float]:
        """Return (should_halt, drawdown_pct)."""
        try:
            if current_equity <= 0:
                logger.warning("Current equity <= 0 (%.2f)", current_equity)
                return True, 100.0

            if current_equity > self.max_equity:
                self.max_equity = current_equity
            dd_pct = 0.0
            if self.max_equity > 0:
                dd_pct = (self.max_equity - current_equity) / self.max_equity * 100.0

            manual_halt = self.cfg.dynasty_halt
            should_halt = manual_halt or dd_pct > self.drawdown_limit_pct

            # Send one-off push alert if halt triggered
            if should_halt and not getattr(self, "_alerted", False):
                try:
                    from metrics_exporter import send_push, ensure_exporter
                    ensure_exporter()
                    msg = (
                        f"🚨 Dynasty HALT – drawdown {dd_pct:.1f}% exceeds limit"
                        if not manual_halt
                        else "⏸ Dynasty HALT – manual flag enabled"
                    )
                    send_push(msg)
                    logger.warning(msg)
                    self._log_risk_event(msg)
                except Exception as exc:
                    logger.error("RiskManager push alert error: %s", exc)
                self._alerted = True

            return should_halt, dd_pct
        except Exception as e:
            logger.error(f"Exception in RiskManager.update_and_check: {e}")
            return True, 100.0

    def _log_risk_event(self, msg: str):
        try:
            with open(self._risk_log_path, 'a') as f:
                f.write(f"{msg}\n")
        except Exception as e:
            logger.error(f"Failed to persist risk event: {e}")

# Singleton helper
_rm: RiskManager | None = None

def get_risk_manager() -> RiskManager:
    global _rm
    if _rm is None:
        _rm = RiskManager()
    return _rm
