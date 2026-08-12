"""US watchlist theme groups (題材族群)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from db import store
from us.watchlist import US_WATCHLIST, us_name

US_SECTOR_LABEL: dict[str, str] = {
    "semi_etf": "半導體 ETF",
    "broad_etf": "大盤 ETF",
    "ai_semi": "AI／龍頭半導體",
    "semi_equip": "半導體設備",
    "memory_legacy": "記憶體／傳統晶片",
}

US_HOT_SECTORS: frozenset[str] = frozenset(
    {"semi_etf", "ai_semi", "semi_equip", "memory_legacy"}
)

# 14 檔美股觀察清單 → 題材族群（每檔唯一歸類）
SYMBOL_US_SECTOR: dict[str, str] = {
    "SOXX": "semi_etf",
    "SMH": "semi_etf",
    "QQQ": "broad_etf",
    "SPY": "broad_etf",
    "TSM": "ai_semi",
    "NVDA": "ai_semi",
    "AMD": "ai_semi",
    "AVGO": "ai_semi",
    "ASML": "semi_equip",
    "AMAT": "semi_equip",
    "LRCX": "semi_equip",
    "KLAC": "semi_equip",
    "MU": "memory_legacy",
    "INTC": "memory_legacy",
}


def classify_us_symbol(symbol: str) -> str:
    return SYMBOL_US_SECTOR.get(symbol, "other")


def compute_us_sector_stats(
    bars: Optional[list[dict[str, Any]]] = None,
    min_members: int = 2,
) -> list[dict[str, Any]]:
    bars = bars if bars is not None else store.latest_us_bars()
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bars:
        sym = b.get("symbol")
        if not sym or sym not in US_WATCHLIST:
            continue
        sector = classify_us_symbol(sym)
        groups[sector].append(
            {
                "symbol": sym,
                "name": us_name(sym),
                "change_pct": b.get("change_pct"),
                "price": b.get("price"),
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
        leader = max(members, key=lambda m: abs(m.get("change_pct") or 0))
        stats.append(
            {
                "code": code,
                "name": US_SECTOR_LABEL.get(code, code),
                "hot": code in US_HOT_SECTORS,
                "count": len(members),
                "avg_change": round(avg, 3),
                "breadth_up": round(up / len(changes), 3),
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


def classify_us_universe() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for sym in sorted(US_WATCHLIST.keys()):
        code = classify_us_symbol(sym)
        rows.append(
            {
                "symbol": sym,
                "name": us_name(sym),
                "sector_code": code,
                "sector_name": US_SECTOR_LABEL.get(code, code),
                "hot": "1" if code in US_HOT_SECTORS else "0",
            }
        )
    return rows
