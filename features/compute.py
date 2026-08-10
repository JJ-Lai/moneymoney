"""Feature helpers from stored bars."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from db import store


def enrich_latest_bars(day: date | None = None) -> list[dict[str, Any]]:
    """Attach volume ratio vs recent same-time-of-day average."""
    day = day or date.today()
    bars = store.latest_bars_1m()
    out: list[dict[str, Any]] = []
    for b in bars:
        ts = b.get("ts") or ""
        tod = ts[11:19] if len(ts) >= 19 else "13:30:00"
        avg = store.avg_volume_cum_same_tod(b["symbol"], tod, lookback_days=20)
        vol_ratio: Optional[float] = None
        vc = b.get("volume_cum")
        if avg and avg > 0 and vc is not None:
            vol_ratio = float(vc) / float(avg)
        enriched = dict(b)
        enriched["vol_ratio"] = vol_ratio
        enriched["trade_date"] = day.isoformat()
        out.append(enriched)
    return out
