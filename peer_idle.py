"""Small, deterministic scheduler for occasional Muchio peer conversations."""
from __future__ import annotations

import datetime
from typing import Any, Dict, Optional


class IdlePeerScheduler:
    """Allow short peer sessions after quiet periods, with daily limits."""

    def __init__(self) -> None:
        self._local_day: Optional[datetime.date] = None
        self._started_today = 0
        self._last_started_at: Optional[float] = None

    @staticmethod
    def _positive_minutes(cfg: Dict[str, Any], key: str, default: int) -> float:
        try:
            return max(1.0, float(cfg.get(key, default)))
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _daily_limit(cfg: Dict[str, Any]) -> int:
        try:
            return max(1, int(float(cfg.get("peer_idle_daily_limit", 8))))
        except (TypeError, ValueError):
            return 8

    def _roll_day(self, now: float) -> None:
        day = datetime.datetime.fromtimestamp(now).date()
        if day != self._local_day:
            self._local_day = day
            self._started_today = 0

    def should_start(self, now: float, last_human_at: float,
                     last_reply_at: float, busy: bool,
                     peer_available: bool, is_leader: bool,
                     cfg: Dict[str, Any]) -> bool:
        """Return true once when this Muchio may initiate an idle session."""
        if not cfg.get("peer_enabled"):
            return False
        if not cfg.get("peer_idle_enabled") or not peer_available or not is_leader:
            return False
        if last_human_at <= 0:
            return False
        if busy or now - last_human_at < self._positive_minutes(
                cfg, "peer_idle_after_minutes", 25) * 60:
            return False
        if last_reply_at > 0 and now - last_reply_at < 30:
            return False
        self._roll_day(now)
        if self._started_today >= self._daily_limit(cfg):
            return False
        if (self._last_started_at is not None
                and now - self._last_started_at < self._positive_minutes(
                    cfg, "peer_idle_interval_minutes", 40) * 60):
            return False
        self._last_started_at = now
        self._started_today += 1
        return True

    def status(self, now: float, last_human_at: float, cfg: Dict[str, Any],
               peer_available: bool, is_leader: bool) -> Dict[str, Any]:
        """Return compact state for the local settings UI."""
        self._roll_day(now)
        limit = self._daily_limit(cfg)
        base = {
            "idle_sessions_today": self._started_today,
            "idle_daily_limit": limit,
            "idle_next_seconds": None,
        }
        if not cfg.get("peer_enabled") or not cfg.get("peer_idle_enabled"):
            return {**base, "idle_state": "off"}
        if not peer_available:
            return {**base, "idle_state": "waiting_peer"}
        if not is_leader:
            return {**base, "idle_state": "waiting_leader"}
        if self._started_today >= limit:
            return {**base, "idle_state": "daily_limit"}
        after_at = last_human_at + self._positive_minutes(
            cfg, "peer_idle_after_minutes", 25) * 60
        interval_at = ((self._last_started_at or 0)
                       + self._positive_minutes(
                           cfg, "peer_idle_interval_minutes", 40) * 60)
        next_at = max(after_at, interval_at)
        return {
            **base,
            "idle_state": "leader_waiting",
            "idle_next_seconds": max(0, int(next_at - now)),
        }
