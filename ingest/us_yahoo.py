"""Fetch US quotes via Yahoo Finance chart API."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx

from config import TZ_NAME, cfg
from db import store
from us.watchlist import us_symbols

logger = logging.getLogger(__name__)

TZ = ZoneInfo(TZ_NAME)
ET = ZoneInfo("America/New_York")
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def is_us_trading_session(now: datetime | None = None) -> bool:
    """Regular US equity session in America/New_York (handles DST)."""
    now = now or datetime.now(TZ)
    et = now.astimezone(ET)
    if et.weekday() >= 5:
        return False
    t = et.timetz().replace(tzinfo=None)
    from datetime import time as dtime

    return dtime(9, 30) <= t <= dtime(16, 0)


def _parse_chart(payload: dict[str, Any], fallback_ts: str) -> Optional[dict[str, Any]]:
    chart = (payload or {}).get("chart") or {}
    result = chart.get("result")
    if not result:
        return None
    item = result[0]
    meta = item.get("meta") or {}
    symbol = (meta.get("symbol") or "").strip()
    if not symbol:
        return None

    price = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    change_pct = None
    if price is not None and prev not in (None, 0):
        change_pct = (float(price) - float(prev)) / float(prev) * 100.0

    indicators = (item.get("indicators") or {}).get("quote") or []
    open_price = high = low = volume = None
    if indicators:
        q = indicators[0]
        opens = [x for x in (q.get("open") or []) if x is not None]
        highs = [x for x in (q.get("high") or []) if x is not None]
        lows = [x for x in (q.get("low") or []) if x is not None]
        vols = [x for x in (q.get("volume") or []) if x is not None]
        if opens:
            open_price = opens[0]
        if highs:
            high = max(highs)
        if lows:
            low = min(lows)
        if vols:
            volume = vols[-1]

    rmt = meta.get("regularMarketTime")
    if rmt:
        ts = datetime.fromtimestamp(int(rmt), tz=TZ).strftime("%Y-%m-%d %H:%M:00")
    else:
        ts = fallback_ts

    return {
        "ts": ts,
        "symbol": symbol,
        "price": float(price) if price is not None else None,
        "change_pct": change_pct,
        "volume": float(volume) if volume is not None else None,
        "open_price": float(open_price) if open_price is not None else None,
        "high": float(high) if high is not None else None,
        "low": float(low) if low is not None else None,
        "prev_close": float(prev) if prev is not None else None,
    }


def fetch_symbol(client: httpx.Client, symbol: str) -> Optional[dict[str, Any]]:
    url = CHART_URL.format(symbol=symbol)
    resp = client.get(url, params={"interval": "5m", "range": "1d"})
    resp.raise_for_status()
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:00")
    return _parse_chart(resp.json(), now)


def ingest_us_once(symbols: list[str] | None = None) -> int:
    symbols = symbols or us_symbols()
    rows: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    with httpx.Client(
        timeout=30.0,
        headers={
            "User-Agent": cfg.user_agent,
            "Accept": "application/json",
        },
        follow_redirects=True,
    ) as client:
        for sym in symbols:
            try:
                row = fetch_symbol(client, sym)
                if row and row.get("price") is not None:
                    rows.append(row)
            except Exception:
                logger.exception("US quote failed: %s", sym)
            time.sleep(0.12)
    n = store.insert_us_bars(rows)
    logger.info(
        "US ingest done: %d/%d symbols in %.1fs",
        n,
        len(symbols),
        time.perf_counter() - t0,
    )
    return n
