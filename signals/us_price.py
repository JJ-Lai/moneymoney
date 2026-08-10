"""US price-move signals for Taiwan-related watchlist."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from config import TZ_NAME
from db import store
from us.watchlist import us_kind, us_name

TZ = ZoneInfo(TZ_NAME)


def evaluate_us_signals(now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(TZ)
    day = now.date()
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    bars = store.latest_us_bars()
    signals: list[dict[str, Any]] = []

    for b in bars:
        symbol = b["symbol"]
        change = b.get("change_pct")
        price = b.get("price")
        kind = us_kind(symbol)
        # Indices/ETFs: slightly lower thresholds; stocks: standard
        thr3, thr5 = (2.0, 3.5) if kind == "etf" else (3.0, 5.0)

        def add(rule_id: str, score: float, note: str) -> None:
            if store.us_signal_exists_today(symbol, rule_id, day):
                return
            signals.append(
                {
                    "ts": ts,
                    "symbol": symbol,
                    "category": "us_price",
                    "rule_id": rule_id,
                    "score": score,
                    "payload": {
                        "note": note,
                        "price": price,
                        "change_pct": change,
                        "name": us_name(symbol),
                        "kind": kind,
                    },
                }
            )

        if change is None:
            continue
        abs_ch = abs(change)
        if abs_ch >= thr5:
            add(
                "US_MOVE_5",
                80 + min(abs_ch, 15),
                f"{us_name(symbol)} 漲跌 {change:.2f}%",
            )
        elif abs_ch >= thr3:
            add(
                "US_MOVE_3",
                55 + min(abs_ch, 10),
                f"{us_name(symbol)} 漲跌 {change:.2f}%",
            )

        # Highlight TSM / semis strongly when moving
        if symbol in ("TSM", "SOXX", "SMH", "NVDA") and abs_ch >= 2.0:
            add(
                "US_TW_LINK",
                70 + min(abs_ch * 3, 20),
                f"台股連動標的 {us_name(symbol)} {change:+.2f}%",
            )

    return signals


def run_us_signals(now: datetime | None = None) -> int:
    sigs = evaluate_us_signals(now)
    return store.insert_us_signals(sigs)
