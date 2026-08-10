"""Hourly intraday digest sender."""

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


def _window_for_send(send_at: datetime) -> tuple[datetime, datetime, str]:
    """Map digest send time to signal window [start, end)."""
    t = send_at.timetz().replace(tzinfo=None)
    d = send_at.date()
    if t.hour == 10 and t.minute == 0:
        start = datetime(d.year, d.month, d.day, 9, 0, tzinfo=TZ)
        end = datetime(d.year, d.month, d.day, 10, 0, tzinfo=TZ)
    elif t.hour == 11 and t.minute == 0:
        start = datetime(d.year, d.month, d.day, 10, 0, tzinfo=TZ)
        end = datetime(d.year, d.month, d.day, 11, 0, tzinfo=TZ)
    elif t.hour == 12 and t.minute == 0:
        start = datetime(d.year, d.month, d.day, 11, 0, tzinfo=TZ)
        end = datetime(d.year, d.month, d.day, 12, 0, tzinfo=TZ)
    else:
        # 13:35 covers 12:00–13:30
        start = datetime(d.year, d.month, d.day, 12, 0, tzinfo=TZ)
        end = datetime(d.year, d.month, d.day, 13, 30, tzinfo=TZ)
    label = f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"
    return start, end, label


def hour_bucket(send_at: datetime) -> str:
    return send_at.strftime("%Y-%m-%d %H:%M")


def build_hourly_digest(
    send_at: datetime | None = None,
) -> tuple[str, str, str, list[int], str]:
    send_at = send_at or datetime.now(TZ)
    start, end, label = _window_for_send(send_at)
    signals = store.pending_signals(
        start.strftime("%Y-%m-%d %H:%M:%S"),
        end.strftime("%Y-%m-%d %H:%M:%S"),
    )
    # Also allow signals up to now if end is in the past slightly
    subject, text, html, ids = build_digest_bodies(
        title=f"{send_at.strftime('%H:%M')} digest",
        window_label=label,
        signals=signals,
    )
    return subject, text, html, ids, hour_bucket(send_at)


def send_hourly_digest(
    send_at: datetime | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> str:
    send_at = send_at or datetime.now(TZ)
    bucket = hour_bucket(send_at)
    if not force and store.digest_already_sent("hourly", bucket):
        logger.info("Hourly digest already sent for %s", bucket)
        return "already_sent"

    subject, text, html, ids, bucket = build_hourly_digest(send_at)
    if dry_run:
        logger.info("%s\n%s", subject, text)
        return "dry_run"

    msg_id = send_mail(subject, text, html)
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    store.mark_signals_digested(ids, now)
    store.log_digest("hourly", bucket, now, len(ids), msg_id)
    return msg_id
