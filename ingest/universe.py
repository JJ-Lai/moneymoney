"""Fetch and cache TWSE listed stock universe."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import cfg
from db import store

logger = logging.getLogger(__name__)

# Listed company basic info (TWSE OpenAPI)
UNIVERSE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"


def _parse_rows(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in data:
        symbol = (
            item.get("公司代號")
            or item.get("Code")
            or item.get("code")
            or ""
        ).strip()
        name = (
            item.get("公司簡稱")
            or item.get("公司名稱")
            or item.get("Name")
            or item.get("name")
            or symbol
        ).strip()
        industry = (
            item.get("產業別")
            or item.get("Industry")
            or item.get("產業類別")
            or None
        )
        if not symbol or not symbol.isdigit():
            continue
        # Keep common stocks / ETFs listed on TWSE (4–6 digit codes)
        if len(symbol) < 4 or len(symbol) > 6:
            continue
        rows.append(
            {
                "symbol": symbol,
                "name": name,
                "industry": industry.strip() if isinstance(industry, str) else industry,
            }
        )
    return rows


def refresh_universe(client: httpx.Client | None = None) -> list[str]:
    """Download listed universe and upsert into DB. Returns symbol list."""
    own = client is None
    client = client or httpx.Client(
        timeout=60.0,
        headers={"User-Agent": cfg.user_agent, "Accept": "application/json"},
        follow_redirects=True,
    )
    try:
        resp = client.get(UNIVERSE_URL)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError(f"Unexpected universe payload type: {type(data)}")
        rows = _parse_rows(data)
        if not rows:
            raise ValueError("Universe empty after parse")
        store.upsert_universe(rows)
        symbols = [r["symbol"] for r in rows]
        logger.info("Universe refreshed: %d symbols", len(symbols))
        return symbols
    finally:
        if own:
            client.close()


def get_or_refresh_symbols(force: bool = False) -> list[str]:
    symbols = store.list_symbols()
    if force or not symbols:
        symbols = refresh_universe()
    return symbols
