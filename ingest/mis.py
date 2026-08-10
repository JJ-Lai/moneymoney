"""TWSE MIS 1-minute snapshot ingest for listed stocks."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx

from config import TZ_NAME, cfg
from db import store
from ingest.universe import get_or_refresh_symbols

logger = logging.getLogger(__name__)

MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
TZ = ZoneInfo(TZ_NAME)


def _to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if s in ("", "-", "--", "null", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _parse_msg(msg: dict[str, Any], fallback_ts: str) -> Optional[dict[str, Any]]:
    symbol = (msg.get("c") or "").strip()
    if not symbol:
        return None
    price = _to_float(msg.get("z"))
    prev_close = _to_float(msg.get("y"))
    open_price = _to_float(msg.get("o"))
    high = _to_float(msg.get("h"))
    low = _to_float(msg.get("l"))
    volume_cum = _to_float(msg.get("v"))  # cumulative lots
    volume = _to_float(msg.get("tv"))

    # If latest trade missing, approximate from best bid/ask
    if price is None:
        bids = str(msg.get("b") or "").split("_")
        asks = str(msg.get("a") or "").split("_")
        bid = _to_float(bids[0]) if bids else None
        ask = _to_float(asks[0]) if asks else None
        if bid and ask:
            price = (bid + ask) / 2.0
        else:
            price = bid or ask or prev_close

    change_pct = None
    if price is not None and prev_close not in (None, 0):
        change_pct = (price - prev_close) / prev_close * 100.0

    tlong = msg.get("tlong")
    if tlong and str(tlong).isdigit():
        ts = datetime.fromtimestamp(int(tlong) / 1000.0, tz=TZ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    else:
        d = (msg.get("d") or "").strip()
        t = (msg.get("t") or "").strip()
        if len(d) == 8 and t:
            ts = f"{d[0:4]}-{d[4:6]}-{d[6:8]} {t}"
        else:
            ts = fallback_ts

    # Snap to minute for bars_1m key stability within the same poll minute
    try:
        dt = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
        ts = dt.strftime("%Y-%m-%d %H:%M:00")
    except ValueError:
        ts = fallback_ts

    return {
        "ts": ts,
        "symbol": symbol,
        "price": price,
        "change_pct": change_pct,
        "volume": volume,
        "volume_cum": volume_cum,
        "open_price": open_price,
        "high": high,
        "low": low,
        "prev_close": prev_close,
    }


def _parse_payload(text: str) -> dict[str, Any]:
    """Parse MIS body; tolerate BOM / leading junk."""
    raw = (text or "").strip().lstrip("\ufeff")
    if not raw:
        raise ValueError("empty MIS response")
    # Some bad responses prepend HTML/newlines before JSON object
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"non-JSON MIS response: {raw[:80]!r}")
    return json.loads(raw[start : end + 1])


def fetch_batch(
    client: httpx.Client,
    symbols: list[str],
    *,
    retries: int = 3,
) -> list[dict[str, Any]]:
    if not symbols:
        return []

    ex_ch = "|".join(f"tse_{s}.tw" for s in symbols)
    params = {"ex_ch": ex_ch, "json": "1", "delay": "0"}
    last_err: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            resp = client.get(MIS_URL, params=params)
            resp.raise_for_status()
            payload = _parse_payload(resp.text)
            msgs = payload.get("msgArray") or []
            now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:00")
            rows: list[dict[str, Any]] = []
            for msg in msgs:
                if not isinstance(msg, dict):
                    continue
                parsed = _parse_msg(msg, now)
                if parsed and parsed.get("price") is not None:
                    rows.append(parsed)
            return rows
        except Exception as exc:
            last_err = exc
            time.sleep(0.4 * attempt)

    # Split and retry halves when a large batch keeps failing
    if len(symbols) > 1:
        mid = len(symbols) // 2
        logger.warning(
            "MIS batch of %d failed (%s); splitting",
            len(symbols),
            last_err,
        )
        left = fetch_batch(client, symbols[:mid], retries=2)
        time.sleep(0.25)
        right = fetch_batch(client, symbols[mid:], retries=2)
        return left + right

    raise RuntimeError(f"MIS fetch failed for {symbols}: {last_err}") from last_err


def ingest_once(symbols: list[str] | None = None) -> int:
    """Fetch all listed symbols in batches and store 1m bars. Returns row count."""
    symbols = symbols or get_or_refresh_symbols()
    if not symbols:
        logger.warning("No symbols to ingest")
        return 0

    batch_size = max(10, min(cfg.mis_batch_size, 50))
    batches = _chunks(symbols, batch_size)
    total = 0
    failed = 0
    t0 = time.perf_counter()
    with httpx.Client(
        timeout=45.0,
        headers={
            "User-Agent": cfg.user_agent,
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://mis.twse.com.tw/stock/index.jsp",
        },
        follow_redirects=True,
    ) as client:
        for i, batch in enumerate(batches):
            try:
                rows = fetch_batch(client, batch)
                total += store.insert_bars_1m(rows)
            except Exception:
                failed += 1
                logger.exception("MIS batch %d/%d failed", i + 1, len(batches))
            time.sleep(0.25)

    elapsed = time.perf_counter() - t0
    logger.info(
        "MIS ingest done: %d rows in %.1fs (%d batches, %d failed)",
        total,
        elapsed,
        len(batches),
        failed,
    )
    return total


def is_trading_session(now: datetime | None = None) -> bool:
    now = now or datetime.now(TZ)
    if now.weekday() >= 5:
        return False
    t = now.timetz().replace(tzinfo=None)
    return cfg.market_open <= t <= cfg.market_close
