"""Separate US-market email digests."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import TZ_NAME, cfg
from db import store
from digest.format import build_sector_section_lines, select_top_symbols, summarize_stock
from mailer.smtp import send_mail
from us.sectors import US_SECTOR_LABEL
from us.watchlist import us_name

logger = logging.getLogger(__name__)
TZ = ZoneInfo(TZ_NAME)

DISCLAIMER = (
    "資料來源 Yahoo Finance（可能延遲）。"
    "本信為美股／與台股相關標的監控，與台股信分開寄送。非投資建議。"
)


def _format_bodies(
    title: str,
    window_label: str,
    signals: list[dict],
) -> tuple[str, str, str, list[int]]:
    ranked, by_symbol, scores = select_top_symbols(
        signals, top_n=min(cfg.digest_top_n, 14)
    )
    ids: list[int] = []
    for sym in ranked:
        for s in by_symbol[sym]:
            if s.get("id") is not None:
                ids.append(int(s["id"]))

    sector_lines = build_sector_section_lines(
        signals,
        top_n=5,
        category="us_sector",
        label_map=US_SECTOR_LABEL,
    )
    for s in signals:
        if s.get("category") != "us_sector" or s.get("id") is None:
            continue
        sid = int(s["id"])
        if sid not in ids:
            ids.append(sid)

    subject = f"[美股監控] {title}｜{len(ranked)} 檔重點"
    lines = [
        "以下是本時段重點（每檔一句話）：",
        f"時段：{window_label}",
        "",
    ]
    html_items: list[str] = []

    if not ranked:
        lines.append("本時段沒有需要特別注意的標的。")
        html_items.append("<p>本時段沒有需要特別注意的標的。</p>")
    else:
        for i, sym in enumerate(ranked, 1):
            name = us_name(sym)
            what = summarize_stock(by_symbol[sym])
            line = f"{i}. {sym} {name}：{what}"
            lines.append(line)
            html_items.append(
                f"<li style='margin:8px 0'><b>{sym} {name}</b>：{what}</li>"
            )

    if sector_lines:
        lines.append("")
        lines.append("【題材族群】")
        lines.extend(sector_lines)

    lines.extend(["", DISCLAIMER])
    text = "\n".join(lines)
    html = f"""
    <html><body style="font-family:Microsoft JhengHei,sans-serif;font-size:15px;color:#222">
    <p><b>{title}</b><br>時段：{window_label}</p>
    <p>以下是本時段重點（每檔一句話）：</p>
    <ol style="padding-left:1.2rem">
      {''.join(html_items) if ranked else ''}
    </ol>
    {f"<p><b>【題材族群】</b></p><ul>{''.join(f'<li>{l}</li>' for l in sector_lines)}</ul>" if sector_lines else ""}
    <p style="color:#888;font-size:12px">{DISCLAIMER}</p>
    </body></html>
    """
    return subject, text, html, ids


def send_us_hourly_digest(
    send_at: datetime | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> str:
    send_at = send_at or datetime.now(TZ)
    end = send_at.replace(second=0, microsecond=0)
    start = end - timedelta(hours=1)
    bucket = f"us {end.strftime('%Y-%m-%d %H:%M')}"
    if not force and store.digest_already_sent("us_hourly", bucket):
        logger.info("US hourly already sent: %s", bucket)
        return "already_sent"

    signals = store.us_pending_signals(
        start.strftime("%Y-%m-%d %H:%M:%S"),
        end.strftime("%Y-%m-%d %H:%M:%S"),
    )
    # also include undigested from same calendar day with high score if window empty
    if not signals:
        signals = [
            s
            for s in store.us_signals_for_day(send_at.date(), pending_only=True)
            if s["ts"] >= start.strftime("%Y-%m-%d %H:%M:%S")
        ]

    subject, text, html, ids = _format_bodies(
        title=f"美股 {end.strftime('%H:%M')} digest",
        window_label=f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')} (台北)",
        signals=signals,
    )
    if dry_run:
        logger.info("%s\n%s", subject, text)
        return "dry_run"

    msg_id = send_mail(subject, text, html)
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    store.mark_us_signals_digested(ids, now)
    store.log_digest("us_hourly", bucket, now, len(ids), msg_id)
    return msg_id


def send_us_eod_digest(
    send_at: datetime | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> str:
    send_at = send_at or datetime.now(TZ)
    day = send_at.astimezone(ZoneInfo("America/New_York")).date()
    # Use Taipei calendar day of send for signal query; also pull ET session day bars
    bucket = f"us eod {day.isoformat()}"
    if not force and store.digest_already_sent("us_eod", bucket):
        logger.info("US EOD already sent: %s", bucket)
        return "already_sent"

    # Collect pending from last 24h Taipei
    since = (send_at - timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S")
    until = send_at.strftime("%Y-%m-%d %H:%M:%S")
    signals = store.us_pending_signals(since, until)
    if not signals:
        signals = store.us_signals_for_day(send_at.date(), pending_only=True)
        signals += store.us_signals_for_day(
            (send_at - timedelta(days=1)).date(), pending_only=True
        )

    # Snapshot table of all watchlist latest
    bars = store.latest_us_bars()
    extra_lines = [
        f"{b['symbol']} {us_name(b['symbol'])} "
        f"{b.get('price')} ({(b.get('change_pct') or 0):+.2f}%)"
        for b in sorted(bars, key=lambda x: abs(x.get("change_pct") or 0), reverse=True)
    ]

    subject, text, html, ids = _format_bodies(
        title=f"美股盤後日結 {day.isoformat()}",
        window_label=f"美東交易日 {day.isoformat()}",
        signals=signals,
    )
    text = (
        text.replace(DISCLAIMER, "").rstrip()
        + "\n\n【收盤快照】\n"
        + "\n".join(extra_lines)
        + f"\n\n{DISCLAIMER}"
    )
    html = html.replace(
        f'<p style="color:#888;font-size:12px">{DISCLAIMER}</p>',
        "<p><b>收盤快照</b></p><ol style='padding-left:1.2rem'>"
        + "".join(f"<li>{line}</li>" for line in extra_lines)
        + f'</ol><p style="color:#888;font-size:12px">{DISCLAIMER}</p>',
    )

    if dry_run:
        logger.info("%s\n%s", subject, text)
        return "dry_run"

    msg_id = send_mail(subject, text, html)
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    store.mark_us_signals_digested(ids, now)
    store.log_digest("us_eod", bucket, now, len(ids), msg_id)
    return msg_id
