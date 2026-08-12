"""Sector-level trend signals (題材族群綜合指標)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from db import store
from sectors.aggregate import compute_sector_stats
from sectors.taxonomy import HOT_SECTORS, SECTOR_LABEL

MIN_MEMBERS = 5
AVG_MOVE_THRESH = 1.5
BREADTH_THRESH = 0.65


def evaluate_sector_trends(now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now()
    day = now.date() if isinstance(now, datetime) else date.today()
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    stats = compute_sector_stats(min_members=MIN_MEMBERS)
    signals: list[dict[str, Any]] = []

    for s in stats:
        code = s["code"]
        avg = s["avg_change"]
        breadth = s["breadth_up"]
        label = s["name"]
        leader = f"{s.get('leader_symbol')} {s.get('leader_name')}"
        leader_ch = s.get("leader_change")
        leader_part = ""
        if isinstance(leader_ch, (int, float)):
            leader_part = f" {leader_ch:+.2f}%"

        def add(rule_id: str, score: float, note: str, extra: dict | None = None) -> None:
            if store.signal_already_digested_today(code, rule_id, day):
                return
            payload = {
                "note": note,
                "sector_code": code,
                "sector_name": label,
                "avg_change": avg,
                "breadth_up": breadth,
                "count": s["count"],
                "leader": leader,
                "leader_change": leader_ch,
                "hot": code in HOT_SECTORS,
            }
            if extra:
                payload.update(extra)
            signals.append(
                {
                    "ts": ts,
                    "symbol": code,
                    "category": "sector",
                    "rule_id": rule_id,
                    "score": score,
                    "payload": payload,
                }
            )

        abs_avg = abs(avg)
        if avg >= AVG_MOVE_THRESH:
            add(
                "SECTOR_UP",
                70 + min(abs_avg * 8, 20) + (5 if code in HOT_SECTORS else 0),
                f"【{label}】族群平均上漲 {avg:.2f}%，"
                f"{s['up_count']}/{s['count']} 檔上漲；領漲 {leader}{leader_part}",
            )
        elif avg <= -AVG_MOVE_THRESH:
            add(
                "SECTOR_DOWN",
                70 + min(abs_avg * 8, 20) + (5 if code in HOT_SECTORS else 0),
                f"【{label}】族群平均下跌 {avg:.2f}%，"
                f"{s['down_count']}/{s['count']} 檔下跌；領跌 {leader}{leader_part}",
            )

        if breadth >= BREADTH_THRESH and avg >= 0.8:
            add(
                "SECTOR_BREADTH_UP",
                65 + min(breadth * 30, 25),
                f"【{label}】多頭擴散 {breadth * 100:.0f}% 成分股上漲（{s['up_count']}/{s['count']}）",
            )
        elif breadth <= (1 - BREADTH_THRESH) and avg <= -0.8:
            add(
                "SECTOR_BREADTH_DOWN",
                65 + min((1 - breadth) * 30, 25),
                f"【{label}】空頭擴散 {(1 - breadth) * 100:.0f}% 成分股下跌（{s['down_count']}/{s['count']}）",
            )

    return signals
