"""End-of-day market data: daily bars, institutional flow, events."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx

from config import TZ_NAME, cfg
from db import store

logger = logging.getLogger(__name__)
TZ = ZoneInfo(TZ_NAME)

STOCK_DAY_ALL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
NOTICE = "https://openapi.twse.com.tw/v1/announcement/notice"
DISPOSAL = "https://openapi.twse.com.tw/v1/announcement/punish"
MATERIAL = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"

NEWS_KEYWORDS = (
    "減資",
    "併購",
    "合併",
    "虧損",
    "股東會",
    "重整",
    "下市",
    "停工",
    "火災",
    "重大訊息",
)


def _to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=90.0,
        headers={"User-Agent": cfg.user_agent, "Accept": "application/json"},
        follow_redirects=True,
    )


def ingest_daily_bars(trade_date: str | None = None) -> int:
    """Load TWSE STOCK_DAY_ALL into bars_1d."""
    with _client() as client:
        resp = client.get(STOCK_DAY_ALL)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, list):
        logger.warning("STOCK_DAY_ALL unexpected payload")
        return 0

    today = trade_date or datetime.now(TZ).strftime("%Y-%m-%d")
    rows: list[dict[str, Any]] = []
    for item in data:
        symbol = (item.get("Code") or item.get("證券代號") or "").strip()
        if not symbol:
            continue
        # Date field may be in item; prefer provided trade_date
        rows.append(
            {
                "trade_date": today,
                "symbol": symbol,
                "open": _to_float(item.get("OpeningPrice") or item.get("開盤價")),
                "high": _to_float(item.get("HighestPrice") or item.get("最高價")),
                "low": _to_float(item.get("LowestPrice") or item.get("最低價")),
                "close": _to_float(item.get("ClosingPrice") or item.get("收盤價")),
                "volume": _to_float(
                    item.get("TradeVolume") or item.get("成交股數")
                ),
            }
        )
    n = store.insert_bars_1d(rows)
    logger.info("Daily bars ingested: %d for %s", n, today)
    return n


def ingest_institutional(trade_date: str | None = None) -> int:
    """Three institutional investors via TWSE T86 JSON report."""
    if trade_date:
        ymd = trade_date.replace("-", "")
        candidates = [ymd]
    else:
        d = datetime.now(TZ).date()
        candidates = []
        for i in range(14):
            day = d - timedelta(days=i)
            if day.weekday() < 5:
                candidates.append(day.strftime("%Y%m%d"))

    payload = None
    used_ymd = None
    with _client() as client:
        for ymd in candidates:
            url = (
                "https://www.twse.com.tw/rwd/zh/fund/T86"
                f"?response=json&date={ymd}&selectType=ALLBUT0999"
            )
            try:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                logger.exception("T86 fetch failed for %s", ymd)
                continue
            if data.get("stat") == "OK" and data.get("data"):
                payload = data
                used_ymd = ymd
                break

    if not payload or not used_ymd:
        logger.warning("T86 no data found for recent dates")
        return 0

    d_iso = f"{used_ymd[0:4]}-{used_ymd[4:6]}-{used_ymd[6:8]}"
    fields = payload.get("fields") or []
    idx = {name: i for i, name in enumerate(fields)}

    def col(row: list, *names: str) -> Optional[float]:
        for name in names:
            if name in idx and idx[name] < len(row):
                return _to_float(row[idx[name]])
        return None

    rows: list[dict[str, Any]] = []
    for row in payload["data"]:
        if not row:
            continue
        symbol = str(row[idx.get("證券代號", 0)]).strip()
        if not symbol:
            continue
        rows.append(
            {
                "trade_date": d_iso,
                "symbol": symbol,
                "foreign_net": col(
                    row,
                    "外陸資買賣超股數(不含外資自營商)",
                    "外資買賣超股數",
                ),
                "trust_net": col(row, "投信買賣超股數"),
                "dealer_net": col(row, "自營商買賣超股數"),
            }
        )
    n = store.insert_institutional(rows)
    logger.info("Institutional ingested: %d for %s", n, d_iso)
    return n


def _event_rows_from_list(
    data: list[dict[str, Any]],
    event_type: str,
    severity: int,
    now_iso: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in data:
        symbol = (
            item.get("Code")
            or item.get("證券代號")
            or item.get("公司代號")
            or None
        )
        if isinstance(symbol, str):
            symbol = symbol.strip() or None
        title = (
            item.get("Name")
            or item.get("證券名稱")
            or item.get("主旨")
            or item.get("Subject")
            or item.get("事由")
            or str(item)
        )
        if isinstance(title, str):
            title = title.strip()[:300]
        else:
            title = str(title)[:300]
        rows.append(
            {
                "ts": now_iso,
                "symbol": symbol,
                "event_type": event_type,
                "title": title,
                "severity": severity,
            }
        )
    return rows


def ingest_events() -> int:
    now_iso = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    rows: list[dict[str, Any]] = []
    with _client() as client:
        for url, etype, sev in (
            (NOTICE, "WATCH_LIST", 3),
            (DISPOSAL, "DISPOSAL", 4),
        ):
            try:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    rows.extend(_event_rows_from_list(data, etype, sev, now_iso))
            except Exception:
                logger.exception("Failed fetching %s", etype)

        try:
            resp = client.get(MATERIAL)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    title = str(
                        item.get("主旨")
                        or item.get("Subject")
                        or item.get("事由")
                        or item
                    )
                    if not any(k in title for k in NEWS_KEYWORDS):
                        continue
                    symbol = (
                        item.get("公司代號")
                        or item.get("Code")
                        or item.get("證券代號")
                    )
                    if isinstance(symbol, str):
                        symbol = symbol.strip()
                    rows.append(
                        {
                            "ts": now_iso,
                            "symbol": symbol,
                            "event_type": "MATERIAL_NEWS",
                            "title": title.strip()[:300],
                            "severity": 3,
                        }
                    )
        except Exception:
            logger.exception("Failed fetching MATERIAL_NEWS")

    n = store.insert_events(rows)
    logger.info("Events ingested: %d", n)
    return n


def run_eod_ingest(trade_date: str | None = None) -> dict[str, int]:
    return {
        "bars_1d": ingest_daily_bars(trade_date),
        "institutional": ingest_institutional(trade_date),
        "events": ingest_events(),
    }
