"""US watchlist linked to Taiwan / semiconductor theme."""

from __future__ import annotations

# symbol -> (中文短名, 類型 etf|stock)
US_WATCHLIST: dict[str, tuple[str, str]] = {
    "SOXX": ("費半ETF", "etf"),
    "SMH": ("半導體ETF", "etf"),
    "QQQ": ("那斯達克100", "etf"),
    "SPY": ("標普500", "etf"),
    "TSM": ("台積電ADR", "stock"),
    "NVDA": ("輝達", "stock"),
    "AMD": ("超微", "stock"),
    "AVGO": ("博通", "stock"),
    "ASML": ("艾司摩爾", "stock"),
    "AMAT": ("應用材料", "stock"),
    "LRCX": ("科林研發", "stock"),
    "KLAC": ("科磊", "stock"),
    "MU": ("美光", "stock"),
    "INTC": ("英特爾", "stock"),
}


def us_symbols() -> list[str]:
    return list(US_WATCHLIST.keys())


def us_name(symbol: str) -> str:
    return US_WATCHLIST.get(symbol, (symbol, ""))[0]


def us_kind(symbol: str) -> str:
    return US_WATCHLIST.get(symbol, ("", "stock"))[1]
