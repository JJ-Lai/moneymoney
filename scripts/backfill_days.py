"""Optional: backfill recent daily bars via STOCK_DAY_ALL (latest day only).

TWSE OpenAPI STOCK_DAY_ALL provides the most recent trading day snapshot.
For multi-day history, re-run after each session or extend with per-stock STOCK_DAY.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import store
from ingest.eod import ingest_daily_bars, ingest_events, ingest_institutional

logging.basicConfig(level=logging.INFO)


def main() -> None:
    store.init_db()
    print("bars:", ingest_daily_bars())
    print("institutional:", ingest_institutional())
    print("events:", ingest_events())


if __name__ == "__main__":
    main()
