"""End-of-day digest email."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from config import TZ_NAME
from db import store
from digest.format import build_digest_bodies
from mailer.smtp import send_mail

logger = logging.getLogger(__name__)
TZ = ZoneInfo(TZ_NAME)


def _extra_sections(day: str) -> list[tuple[str, list[str]]]:
    from digest.format import is_mail_worthy_symbol

    sections: list[tuple[str, list[str]]] = []
    names = store.get_symbol_names()
    inst_day = store.latest_institutional_date() or day
    inst = store.get_institutional(inst_day)
    if inst:
        by_foreign = sorted(
            [r for r in inst if is_mail_worthy_symbol(str(r.get("symbol") or ""))],
            key=lambda r: abs(r.get("foreign_net") or 0),
            reverse=True,
        )[:8]
        lines = []
        for r in by_foreign:
            sym = r["symbol"]
            name = names.get(sym, sym)
            f = r.get("foreign_net") or 0
            direction = "買超" if f > 0 else "賣超"
            lines.append(f"{sym} {name}：外資今日{direction} {abs(f):,.0f} 股")
        if lines:
            sections.append(("法人動向", lines))

    events = store.get_events_since(f"{day} 00:00:00")
    if events:
        lines = []
        seen = set()
        for e in events:
            sym = str(e.get("symbol") or "")
            if not is_mail_worthy_symbol(sym) or sym in seen:
                continue
            seen.add(sym)
            et = e.get("event_type")
            name = names.get(sym, sym)
            if et == "DISPOSAL":
                lines.append(f"{sym} {name}：被列為處置股")
            elif et == "WATCH_LIST":
                lines.append(f"{sym} {name}：被列為注意股")
            else:
                title = str(e.get("title") or "")[:36]
                lines.append(f"{sym} {name}：{title}")
            if len(lines) >= 10:
                break
        if lines:
            sections.append(("注意／處置／訊息", lines))
    return sections


def build_eod_digest(send_at: datetime | None = None):
    send_at = send_at or datetime.now(TZ)
    day = send_at.date().isoformat()
    signals = store.all_pending_signals_for_day(send_at.date())
    # Prefer including institutional/events; also leftover intraday
    subject, text, html, ids = build_digest_bodies(
        title=f"{day} 盤後日結",
        window_label=f"{day} 全日",
        signals=signals,
        extra_sections=_extra_sections(day),
    )
    bucket = f"{day} eod"
    return subject, text, html, ids, bucket


def send_eod_digest(
    send_at: datetime | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> str:
    send_at = send_at or datetime.now(TZ)
    subject, text, html, ids, bucket = build_eod_digest(send_at)
    if not force and store.digest_already_sent("eod", bucket):
        logger.info("EOD digest already sent for %s", bucket)
        return "already_sent"
    if dry_run:
        logger.info("%s\n%s", subject, text)
        return "dry_run"
    msg_id = send_mail(subject, text, html)
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    store.mark_signals_digested(ids, now)
    store.log_digest("eod", bucket, now, len(ids), msg_id)
    return msg_id
