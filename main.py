"""Entry point: scheduler + CLI (TW + US)."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import TZ_NAME, cfg
from db import store
from digest import eod as eod_digest
from digest import hourly as hourly_digest
from digest import us_mail
from ingest import eod as eod_ingest
from ingest import mis
from ingest import us_yahoo
from ingest.universe import get_or_refresh_symbols
from mailer.smtp import send_mail, smtp_configured
from signals.engine import run_eod_signals, run_intraday_signals
from signals.us_price import run_us_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(
            stream=open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
        )
    ],
)
logger = logging.getLogger("main")
TZ = ZoneInfo(TZ_NAME)
ET = ZoneInfo("America/New_York")


def job_minute() -> None:
    now = datetime.now(TZ)
    if not mis.is_trading_session(now):
        return
    try:
        get_or_refresh_symbols()
        mis.ingest_once()
        run_intraday_signals(now)
    except Exception:
        logger.exception("Minute job failed")


def job_us_quote() -> None:
    if not us_yahoo.is_us_trading_session():
        return
    try:
        us_yahoo.ingest_us_once()
        run_us_signals()
    except Exception:
        logger.exception("US quote job failed")


def job_hourly_digest(hour: int, minute: int) -> None:
    now = datetime.now(TZ)
    send_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    try:
        hourly_digest.send_hourly_digest(send_at=send_at)
    except Exception:
        logger.exception("Hourly digest failed")


def job_us_hourly_digest() -> None:
    """Send US digest hourly during regular US session (America/New_York)."""
    et = datetime.now(ET)
    if et.weekday() >= 5:
        return
    t = et.timetz().replace(tzinfo=None)
    if not (dtime(10, 0) <= t <= dtime(16, 5)):
        return
    try:
        us_mail.send_us_hourly_digest(send_at=datetime.now(TZ))
    except Exception:
        logger.exception("US hourly digest failed")


def job_eod() -> None:
    now = datetime.now(TZ)
    if now.weekday() >= 5:
        return
    try:
        eod_ingest.run_eod_ingest()
        run_eod_signals()
        eod_digest.send_eod_digest(send_at=now)
    except Exception:
        logger.exception("EOD job failed")


def job_us_eod() -> None:
    try:
        us_yahoo.ingest_us_once()
        run_us_signals()
        us_mail.send_us_eod_digest(send_at=datetime.now(TZ))
    except Exception:
        logger.exception("US EOD job failed")


def run_once() -> None:
    store.init_db()
    get_or_refresh_symbols(force=True)
    if mis.is_trading_session():
        mis.ingest_once()
        run_intraday_signals()
    else:
        logger.info("Outside TW session; skipped MIS ingest")
        run_intraday_signals()


def run_us_once() -> None:
    store.init_db()
    n = us_yahoo.ingest_us_once()
    s = run_us_signals()
    logger.info("US once: bars=%s signals=%s session=%s", n, s, us_yahoo.is_us_trading_session())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="台股／美股監控告警系統")
    parser.add_argument("--once", action="store_true", help="台股：跑一次擷取+訊號")
    parser.add_argument("--us-once", action="store_true", help="美股：跑一次擷取+訊號")
    parser.add_argument(
        "--dry-run-digest",
        choices=["hourly", "eod", "us_hourly", "us_eod"],
        help="印出 digest 不寄信",
    )
    parser.add_argument("--test-mail", action="store_true", help="寄一封測試信")
    parser.add_argument("--init-db", action="store_true", help="只初始化資料庫")
    parser.add_argument("--eod-now", action="store_true", help="立刻跑台股盤後流程")
    parser.add_argument("--us-eod-now", action="store_true", help="立刻跑美股盤後流程")
    args = parser.parse_args(argv)

    store.init_db()

    if args.init_db:
        logger.info("DB initialized at %s", cfg.db_path)
        return 0

    if args.test_mail:
        if not smtp_configured():
            logger.error("SMTP not configured")
            return 1
        send_mail(
            "[台股監控] 測試信",
            "這是一封測試信。若收到表示 SMTP 設定正確。\n非投資建議。",
            "<p>這是一封測試信。若收到表示 SMTP 設定正確。</p><p>非投資建議。</p>",
        )
        return 0

    if args.dry_run_digest == "hourly":
        hourly_digest.send_hourly_digest(dry_run=True, force=True)
        return 0
    if args.dry_run_digest == "eod":
        eod_digest.send_eod_digest(dry_run=True, force=True)
        return 0
    if args.dry_run_digest == "us_hourly":
        us_mail.send_us_hourly_digest(dry_run=True, force=True)
        return 0
    if args.dry_run_digest == "us_eod":
        us_mail.send_us_eod_digest(dry_run=True, force=True)
        return 0

    if args.eod_now:
        eod_ingest.run_eod_ingest()
        run_eod_signals()
        logger.info("TW EOD ingest + signals done")
        return 0

    if args.us_eod_now:
        run_us_once()
        us_mail.send_us_eod_digest(force=True)
        return 0

    if args.once:
        run_once()
        return 0

    if args.us_once:
        run_us_once()
        return 0

    get_or_refresh_symbols(force=True)
    scheduler = BlockingScheduler(timezone=TZ_NAME)

    # Taiwan
    scheduler.add_job(job_minute, CronTrigger(minute="*", second=5, timezone=TZ_NAME))
    for t in cfg.hourly_digest_times:
        scheduler.add_job(
            job_hourly_digest,
            CronTrigger(hour=t.hour, minute=t.minute, second=10, timezone=TZ_NAME),
            kwargs={"hour": t.hour, "minute": t.minute},
            id=f"hourly_{t.hour:02d}{t.minute:02d}",
        )
    et = cfg.eod_digest_time
    scheduler.add_job(
        job_eod,
        CronTrigger(hour=et.hour, minute=et.minute, second=20, timezone=TZ_NAME),
        id="eod",
    )

    # US — every 2 minutes quotes; hourly digest in ET session; EOD 16:20 ET
    scheduler.add_job(
        job_us_quote,
        CronTrigger(minute="*/2", second=20, timezone=TZ_NAME),
        id="us_quote",
    )
    scheduler.add_job(
        job_us_hourly_digest,
        CronTrigger(minute=5, second=15, timezone="America/New_York"),
        id="us_hourly",
    )
    scheduler.add_job(
        job_us_eod,
        CronTrigger(hour=16, minute=20, second=30, timezone="America/New_York"),
        id="us_eod",
        day_of_week="mon-fri",
    )

    logger.info(
        "Scheduler started (TW+US). DB=%s digest_top_n=%s",
        cfg.db_path,
        cfg.digest_top_n,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
