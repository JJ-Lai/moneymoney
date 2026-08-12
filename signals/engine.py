"""Signal engine orchestrator."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from config import TZ_NAME
from db import store
from signals.events import evaluate_events
from signals.institutional import evaluate_institutional
from signals.price_volume import evaluate_price_volume
from signals.sector import evaluate_sector_trends
from signals.technical import evaluate_technical

logger = logging.getLogger(__name__)
TZ = ZoneInfo(TZ_NAME)


def run_intraday_signals(now: datetime | None = None) -> int:
    now = now or datetime.now(TZ)
    signals: list[dict[str, Any]] = []
    signals.extend(evaluate_price_volume(now))
    signals.extend(evaluate_technical(now))
    # Events may appear during day if ingested; safe to evaluate
    signals.extend(evaluate_events(now, lookback_hours=6))
    signals.extend(evaluate_sector_trends(now))
    n = store.insert_signals(signals)
    logger.info("Intraday signals inserted: %d", n)
    return n


def run_eod_signals(trade_date: str | None = None, now: datetime | None = None) -> int:
    now = now or datetime.now(TZ)
    signals: list[dict[str, Any]] = []
    signals.extend(evaluate_institutional(trade_date=trade_date, now=now))
    signals.extend(evaluate_events(now, lookback_hours=24))
    # Refresh price_volume / technical with final snapshot if any
    signals.extend(evaluate_price_volume(now))
    signals.extend(evaluate_technical(now))
    signals.extend(evaluate_sector_trends(now))
    n = store.insert_signals(signals)
    logger.info("EOD signals inserted: %d", n)
    return n
