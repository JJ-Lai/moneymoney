"""Price / volume signal rules."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from db import store
from features.compute import enrich_latest_bars


def evaluate_price_volume(now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now()
    day = now.date() if isinstance(now, datetime) else date.today()
    bars = enrich_latest_bars(day)
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    signals: list[dict[str, Any]] = []

    for b in bars:
        symbol = b["symbol"]
        change = b.get("change_pct")
        vol_ratio = b.get("vol_ratio")
        price = b.get("price")

        def add(rule_id: str, score: float, note: str) -> None:
            if store.signal_already_digested_today(symbol, rule_id, day):
                return
            signals.append(
                {
                    "ts": ts,
                    "symbol": symbol,
                    "category": "price_volume",
                    "rule_id": rule_id,
                    "score": score,
                    "payload": {
                        "note": note,
                        "price": price,
                        "change_pct": change,
                        "vol_ratio": vol_ratio,
                        "volume_cum": b.get("volume_cum"),
                    },
                }
            )

        if change is not None:
            abs_ch = abs(change)
            if abs_ch >= 5:
                add(
                    "PX_MOVE_5",
                    80 + min(abs_ch, 10),
                    f"漲跌幅 {change:.2f}% ≥ 5%",
                )
            elif abs_ch >= 3:
                add(
                    "PX_MOVE_3",
                    55 + min(abs_ch, 5),
                    f"漲跌幅 {change:.2f}% ≥ 3%",
                )

        if vol_ratio is not None and vol_ratio >= 2.5:
            add(
                "VOL_SPIKE",
                60 + min(vol_ratio * 5, 25),
                f"量比 {vol_ratio:.2f}x（同時段均量）",
            )

        if change is not None and vol_ratio is not None:
            if change >= 2 and vol_ratio >= 2:
                add(
                    "PX_VOL_UP",
                    85 + min(change, 10),
                    f"上漲 {change:.2f}% 且量比 {vol_ratio:.2f}x",
                )
            if change <= -2 and vol_ratio >= 2:
                add(
                    "PX_VOL_DOWN",
                    85 + min(abs(change), 10),
                    f"下跌 {change:.2f}% 且量比 {vol_ratio:.2f}x",
                )

    return signals
