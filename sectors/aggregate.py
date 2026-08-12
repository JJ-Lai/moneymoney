"""Aggregate sector-level market stats from latest quotes."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from db import store
from sectors.taxonomy import HOT_SECTORS, SECTOR_LABEL, get_sector_for_symbol


def _median(values: list[float]) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def compute_sector_stats(
    bars: Optional[list[dict[str, Any]]] = None,
    min_members: int = 3,
) -> list[dict[str, Any]]:
    """Return per-sector aggregates sorted by |avg_change| desc."""
    bars = bars if bars is not None else store.latest_bars_1m()
    industries = store.get_symbol_industries()
    names = store.get_symbol_names()

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bars:
        sym = b.get("symbol")
        if not sym:
            continue
        sector = get_sector_for_symbol(sym, industries, names)
        ch = b.get("change_pct")
        groups[sector].append(
            {
                "symbol": sym,
                "name": names.get(sym, sym),
                "change_pct": ch,
                "price": b.get("price"),
                "industry": industries.get(sym),
            }
        )

    stats: list[dict[str, Any]] = []
    for code, members in groups.items():
        if len(members) < min_members:
            continue
        changes = [float(m["change_pct"]) for m in members if m.get("change_pct") is not None]
        if not changes:
            continue
        avg = sum(changes) / len(changes)
        up = sum(1 for c in changes if c > 0)
        down = sum(1 for c in changes if c < 0)
        breadth_up = up / len(changes)
        leader = max(members, key=lambda m: abs(m.get("change_pct") or 0))
        stats.append(
            {
                "code": code,
                "name": SECTOR_LABEL.get(code, code),
                "hot": code in HOT_SECTORS,
                "count": len(members),
                "avg_change": round(avg, 3),
                "median_change": round(_median(changes) or 0, 3),
                "breadth_up": round(breadth_up, 3),
                "breadth_down": round(down / len(changes), 3),
                "up_count": up,
                "down_count": down,
                "leader_symbol": leader.get("symbol"),
                "leader_name": leader.get("name"),
                "leader_change": leader.get("change_pct"),
                "members": members,
            }
        )

    stats.sort(key=lambda s: abs(s["avg_change"]), reverse=True)
    return stats


def classify_universe() -> list[dict[str, str]]:
    """Every listed symbol with industry + theme sector."""
    industries = store.get_symbol_industries()
    names = store.get_symbol_names()
    from sectors.taxonomy import industry_label, classify_symbol

    rows: list[dict[str, str]] = []
    for sym in sorted(names.keys()):
        ind = industries.get(sym)
        sector = classify_symbol(sym, ind, names.get(sym))
        rows.append(
            {
                "symbol": sym,
                "name": names[sym],
                "industry_code": ind or "",
                "industry_name": industry_label(ind),
                "sector_code": sector,
                "sector_name": SECTOR_LABEL.get(sector, sector),
                "hot": "1" if sector in HOT_SECTORS else "0",
            }
        )
    return rows
