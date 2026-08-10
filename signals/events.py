"""Event-driven signal rules."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from config import TZ_NAME
from db import store

TZ = ZoneInfo(TZ_NAME)

RULE_MAP = {
    "WATCH_LIST": ("WATCH_LIST", 48),
    "DISPOSAL": ("DISPOSAL", 50),
    "MATERIAL_NEWS": ("MATERIAL_NEWS", 70),
}

EVENT_NOTE = {
    "WATCH_LIST": "被列為注意股",
    "DISPOSAL": "被列為處置股",
}


def _is_listed_equity(symbol: str, universe: set[str]) -> bool:
    """Only common stocks / ETFs — skip warrants."""
    if not symbol or symbol == "MARKET":
        return False
    if not symbol.isdigit():
        return False
    # 權證多為 5–6 碼且以 0 開頭（非 00 ETF）
    if len(symbol) >= 5 and symbol.startswith("0") and not symbol.startswith("00"):
        return False
    if len(symbol) == 4:
        return True
    if symbol.startswith("00") and len(symbol) in (4, 5, 6):
        return symbol in universe or True
    return symbol in universe and len(symbol) <= 6


def evaluate_events(now: datetime | None = None, lookback_hours: int = 24) -> list[dict[str, Any]]:
    now = now or datetime.now(TZ)
    day = now.date()
    since = (now - timedelta(hours=lookback_hours)).strftime("%Y-%m-%d %H:%M:%S")
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    events = store.get_events_since(since)
    universe = set(store.list_symbols())
    signals: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for ev in events:
        symbol = ev.get("symbol") or ""
        if not _is_listed_equity(symbol, universe):
            continue
        # Prefer names that exist in listed universe for disposal/notice
        etype = ev.get("event_type") or "EVENT"
        rule_id, base_score = RULE_MAP.get(etype, (etype, 40))
        key = (symbol, rule_id)
        if key in seen:
            continue
        seen.add(key)

        if store.signal_already_digested_today(symbol, rule_id, day):
            continue

        title = str(ev.get("title") or "").strip()
        if etype == "MATERIAL_NEWS":
            note = f"重大訊息：{title[:40]}" if title else "有重大訊息"
        else:
            note = EVENT_NOTE.get(etype, title or etype)

        signals.append(
            {
                "ts": ts,
                "symbol": symbol,
                "category": "events",
                "rule_id": rule_id,
                "score": base_score,
                "payload": {
                    "note": note,
                    "event_type": etype,
                    "title": title,
                    "severity": ev.get("severity"),
                },
            }
        )
    return signals
