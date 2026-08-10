"""SMTP mail delivery."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config import cfg

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return bool(cfg.smtp_host and cfg.smtp_user and cfg.smtp_password and cfg.mail_to)


def send_mail(
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
) -> str:
    if not smtp_configured():
        raise RuntimeError(
            "SMTP not configured. Set SMTP_* and MAIL_TO in .env"
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.mail_from or cfg.smtp_user
    msg["To"] = cfg.mail_to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(cfg.smtp_user, cfg.smtp_password)
        server.sendmail(msg["From"], [cfg.mail_to], msg.as_string())

    message_id = msg.get("Message-ID") or ""
    logger.info("Mail sent: %s", subject)
    return message_id
