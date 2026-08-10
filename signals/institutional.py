"""Institutional investor signal rules (EOD)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from config import TZ_NAME
from db import store

TZ = ZoneInfo(TZ_NAME)

# Share-count thresholds (股). T86 usually reports 股.
FOREIGN_THRESHOLD = 2_000_000
TRUST_THRESHOLD = 500_000


def evaluate_institutional(
    trade_date: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(TZ)
    day = now.date()
    d = trade_date or store.latest_institutional_date() or day.isoformat()
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    rows = store.get_institutional(d)
    universe = set(store.list_symbols())
    signals: list[dict[str, Any]] = []

    for r in rows:
        symbol = r["symbol"]
        if universe and symbol not in universe:
            continue
        foreign = r.get("foreign_net") or 0.0
        trust = r.get("trust_net") or 0.0

        def add(rule_id: str, score: float, note: str, sym: str = symbol) -> None:
            if store.signal_already_digested_today(sym, rule_id, day):
                return
            signals.append(
                {
                    "ts": ts,
                    "symbol": sym,
                    "category": "institutional",
                    "rule_id": rule_id,
                    "score": score,
                    "payload": {
                        "note": note,
                        "foreign_net": foreign,
                        "trust_net": trust,
                        "dealer_net": r.get("dealer_net"),
                        "trade_date": d,
                    },
                }
            )

        if abs(foreign) >= FOREIGN_THRESHOLD:
            direction = "買超" if foreign > 0 else "賣超"
            add(
                "INST_FOREIGN_BIG",
                70 + min(abs(foreign) / FOREIGN_THRESHOLD * 5, 20),
                f"外資{direction} {foreign:,.0f} 股",
            )
        if abs(trust) >= TRUST_THRESHOLD:
            direction = "買超" if trust > 0 else "賣超"
            add(
                "INST_TRUST_BIG",
                65 + min(abs(trust) / TRUST_THRESHOLD * 5, 20),
                f"投信{direction} {trust:,.0f} 股",
            )
        if (
            abs(foreign) >= FOREIGN_THRESHOLD
            and abs(trust) >= TRUST_THRESHOLD
            and (foreign > 0) == (trust > 0)
        ):
            direction = "買超" if foreign > 0 else "賣超"
            add(
                "INST_TRIPLE",
                90,
                f"外資+投信同向{direction}",
            )

    return signals
