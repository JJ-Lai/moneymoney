"""Runtime configuration for tw-stock-monitor."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TZ_NAME = "Asia/Taipei"


@dataclass(frozen=True)
class Config:
    db_path: Path
    mis_batch_size: int
    digest_top_n: int
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    mail_from: str
    mail_to: str
    # Trading session (Taiwan)
    market_open: time = time(9, 0)
    market_close: time = time(13, 30)
    # Intraday digest send times (local)
    hourly_digest_times: tuple[time, ...] = (
        time(10, 0),
        time(11, 0),
        time(12, 0),
        time(13, 35),
    )
    eod_digest_time: time = time(15, 45)
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )


def load_config() -> Config:
    db = os.getenv("DB_PATH", str(BASE_DIR / "data" / "monitor.db"))
    return Config(
        db_path=Path(db),
        mis_batch_size=int(os.getenv("MIS_BATCH_SIZE", "40")),
        digest_top_n=int(os.getenv("DIGEST_TOP_N", "20")),
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        mail_from=os.getenv("MAIL_FROM", os.getenv("SMTP_USER", "")),
        mail_to=os.getenv("MAIL_TO", ""),
    )


cfg = load_config()
