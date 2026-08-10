"""Technical indicator signal rules (daily bars + latest price)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from db import store


def _sma(values: list[float], n: int) -> Optional[float]:
    if len(values) < n:
        return None
    window = values[-n:]
    return sum(window) / n


def _rsi(closes: list[float], n: int = 14) -> Optional[float]:
    if len(closes) < n + 1:
        return None
    gains = []
    losses = []
    for i in range(-n, 0):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains) / n
    avg_loss = sum(losses) / n
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _ema(values: list[float], n: int) -> list[Optional[float]]:
    out: list[Optional[float]] = [None] * len(values)
    if len(values) < n:
        return out
    k = 2 / (n + 1)
    sma = sum(values[:n]) / n
    out[n - 1] = sma
    prev = sma
    for i in range(n, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def _macd_cross(closes: list[float]) -> Optional[str]:
    if len(closes) < 35:
        return None
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line: list[float] = []
    idx_map: list[int] = []
    for i, (a, b) in enumerate(zip(ema12, ema26)):
        if a is None or b is None:
            continue
        macd_line.append(a - b)
        idx_map.append(i)
    if len(macd_line) < 9:
        return None
    signal = _ema(macd_line, 9)
    if len(signal) < 2 or signal[-1] is None or signal[-2] is None:
        return None
    prev_diff = macd_line[-2] - signal[-2]
    cur_diff = macd_line[-1] - signal[-1]
    if prev_diff <= 0 < cur_diff:
        return "golden"
    if prev_diff >= 0 > cur_diff:
        return "death"
    return None


def evaluate_technical(now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now()
    day = now.date()
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    latest = {b["symbol"]: b for b in store.latest_bars_1m()}
    signals: list[dict[str, Any]] = []

    for symbol, bar in latest.items():
        price = bar.get("price")
        if price is None:
            continue
        hist = store.get_bars_1d(symbol, limit=120)
        closes = [float(h["close"]) for h in hist if h.get("close") is not None]
        # Append today's live price as proxy close for breakout checks
        series = closes + [float(price)]

        def add(rule_id: str, score: float, note: str) -> None:
            if store.signal_already_digested_today(symbol, rule_id, day):
                return
            signals.append(
                {
                    "ts": ts,
                    "symbol": symbol,
                    "category": "technical",
                    "rule_id": rule_id,
                    "score": score,
                    "payload": {
                        "note": note,
                        "price": price,
                        "change_pct": bar.get("change_pct"),
                    },
                }
            )

        if len(closes) >= 20:
            ma20_prev = _sma(closes, 20)
            ma20_now = _sma(series, 20)
            if ma20_prev and ma20_now:
                if closes[-1] <= ma20_prev and price > ma20_now:
                    add("BREAK_MA20", 50, f"上穿 MA20（{ma20_now:.2f}）")
                if closes[-1] >= ma20_prev and price < ma20_now:
                    add("BREAK_MA20", 50, f"下破 MA20（{ma20_now:.2f}）")

        if len(closes) >= 60:
            ma60_prev = _sma(closes, 60)
            ma60_now = _sma(series, 60)
            if ma60_prev and ma60_now:
                if closes[-1] <= ma60_prev and price > ma60_now:
                    add("BREAK_MA60", 58, f"上穿 MA60（{ma60_now:.2f}）")
                if closes[-1] >= ma60_prev and price < ma60_now:
                    add("BREAK_MA60", 58, f"下破 MA60（{ma60_now:.2f}）")

        rsi = _rsi(series, 14)
        ch = bar.get("change_pct") or 0
        if rsi is not None:
            if rsi >= 70 and ch > 0:
                add("RSI_EXT", 45, f"RSI {rsi:.1f} 偏高且上漲")
            elif rsi <= 30 and ch < 0:
                add("RSI_EXT", 45, f"RSI {rsi:.1f} 偏低且下跌")

        cross = _macd_cross(series)
        if cross == "golden":
            add("MACD_CROSS", 52, "MACD 金叉")
        elif cross == "death":
            add("MACD_CROSS", 52, "MACD 死叉")

    return signals
