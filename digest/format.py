"""Format digest emails — plain Chinese, one story per stock."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from config import cfg
from db import store

CATEGORY_LABEL = {
    "price_volume": "價量",
    "technical": "技術",
    "institutional": "法人",
    "events": "事件",
    "us_price": "美股",
}

DISCLAIMER = (
    "資料來源為公開行情，可能有延遲。"
    "本信僅供監控參考，非投資建議。"
)

# rule_id -> 簡短中文（優先用 payload 數字組句）
RULE_ZH = {
    "PX_MOVE_3": "明顯波動",
    "PX_MOVE_5": "大幅波動",
    "VOL_SPIKE": "成交量暴增",
    "PX_VOL_UP": "上漲且爆量",
    "PX_VOL_DOWN": "下跌且爆量",
    "BREAK_MA20": "站上／跌破月線(MA20)",
    "BREAK_MA60": "站上／跌破季線(MA60)",
    "RSI_EXT": "RSI 進入超買或超賣",
    "MACD_CROSS": "MACD 出現交叉",
    "INST_FOREIGN_BIG": "外資大幅買賣超",
    "INST_TRUST_BIG": "投信大幅買賣超",
    "INST_TRIPLE": "外資與投信同向買賣超",
    "WATCH_LIST": "被列為注意股",
    "DISPOSAL": "被列為處置股",
    "MATERIAL_NEWS": "有重大訊息",
    "US_MOVE_3": "明顯波動",
    "US_MOVE_5": "大幅波動",
    "US_TW_LINK": "與台股連動標的波動",
}


def _names() -> dict[str, str]:
    return store.get_symbol_names()


def is_mail_worthy_symbol(symbol: str) -> bool:
    """Drop warrants / odd codes that clutter digests."""
    if not symbol or symbol == "MARKET":
        return False
    if not str(symbol).isdigit():
        # US tickers like NVDA / SOXX are fine for US mail
        return str(symbol).isascii() and str(symbol).isalnum()
    s = str(symbol)
    if len(s) == 4:
        return True
    # TW ETF often 00xx / 00xxx
    if s.startswith("00") and len(s) in (4, 5, 6):
        return True
    # 6-digit starting with 0 → 權證為主，不進信
    if len(s) >= 5 and s.startswith("0"):
        return False
    return len(s) <= 6


def humanize_signal(sig: dict[str, Any]) -> str:
    """One short Chinese clause for a signal."""
    payload = sig.get("payload") or {}
    rule = sig.get("rule_id") or ""
    note = str(payload.get("note") or "").strip()
    change = payload.get("change_pct")
    vol_ratio = payload.get("vol_ratio")

    if rule in ("PX_MOVE_3", "PX_MOVE_5", "US_MOVE_3", "US_MOVE_5", "US_TW_LINK"):
        if isinstance(change, (int, float)):
            direction = "上漲" if change > 0 else "下跌"
            return f"今日{direction} {abs(change):.2f}%"
        return RULE_ZH.get(rule, note or rule)

    if rule == "VOL_SPIKE":
        if isinstance(vol_ratio, (int, float)):
            return f"成交量約為平時 {vol_ratio:.1f} 倍"
        return "成交量明顯放大"

    if rule == "PX_VOL_UP":
        ch = f"{change:.2f}%" if isinstance(change, (int, float)) else ""
        return f"上漲{(' ' + ch) if ch else ''}且爆量"
    if rule == "PX_VOL_DOWN":
        ch = f"{abs(change):.2f}%" if isinstance(change, (int, float)) else ""
        return f"下跌{(' ' + ch) if ch else ''}且爆量"

    if rule == "DISPOSAL":
        return "被列為處置股"
    if rule == "WATCH_LIST":
        return "被列為注意股"
    if rule == "MATERIAL_NEWS":
        title = payload.get("title") or note
        title = str(title).replace("MATERIAL_NEWS:", "").strip()
        if len(title) > 40:
            title = title[:40] + "…"
        return f"重大訊息：{title}" if title else "有重大訊息"

    if rule.startswith("INST_"):
        if "買超" in note or "賣超" in note:
            # e.g. 外資買超 1,234,567 股
            return note
        return RULE_ZH.get(rule, "法人買賣超異常")

    if rule.startswith("BREAK_") or rule in ("RSI_EXT", "MACD_CROSS"):
        # prefer original note if already Chinese
        if note and not note.startswith(rule):
            return note
        return RULE_ZH.get(rule, note or rule)

    # strip duplicated "RULE: RULE:" prefixes
    cleaned = note
    for prefix in (f"{rule}:", "DISPOSAL:", "WATCH_LIST:", "MATERIAL_NEWS:"):
        cleaned = cleaned.replace(prefix, "").strip()
    if cleaned:
        return cleaned
    return RULE_ZH.get(rule, rule)


def summarize_stock(rules: list[dict[str, Any]]) -> str:
    """Merge multiple signals into one readable sentence."""
    # Prefer unique humanized clauses; keep order by score
    ordered = sorted(rules, key=lambda r: float(r.get("score") or 0), reverse=True)
    seen: set[str] = set()
    parts: list[str] = []
    for r in ordered:
        clause = humanize_signal(r)
        if clause in seen:
            continue
        seen.add(clause)
        parts.append(clause)
        if len(parts) >= 3:
            break
    return "；".join(parts)


def select_top_symbols(
    signals: list[dict[str, Any]],
    top_n: int | None = None,
) -> tuple[list[str], dict[str, list[dict[str, Any]]], dict[str, float]]:
    top_n = top_n or cfg.digest_top_n
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scores: dict[str, float] = defaultdict(float)

    for s in signals:
        sym = s["symbol"]
        if not is_mail_worthy_symbol(sym):
            continue
        # Pure disposal/watch on non-mover: slight demote so price action ranks first
        score = float(s.get("score") or 0)
        if s.get("category") == "events" and s.get("rule_id") in ("DISPOSAL", "WATCH_LIST"):
            score = min(score, 50)
        by_symbol[sym].append(s)
        scores[sym] = max(scores[sym], score)

    # Boost symbols that also have price_volume
    for sym, rules in by_symbol.items():
        if any(r.get("category") == "price_volume" for r in rules):
            scores[sym] += 15

    ranked = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_n]
    return ranked, by_symbol, scores


def build_digest_bodies(
    title: str,
    window_label: str,
    signals: list[dict[str, Any]],
    extra_sections: list[tuple[str, list[str]]] | None = None,
) -> tuple[str, str, str, list[int]]:
    """Return subject, text, html, and signal ids included."""
    names = _names()
    ranked, by_symbol, scores = select_top_symbols(signals)
    included_ids: list[int] = []
    for sym in ranked:
        for s in by_symbol[sym]:
            if s.get("id") is not None:
                included_ids.append(int(s["id"]))

    subject = f"[台股監控] {title}｜{len(ranked)} 檔重點"

    lines = [
        "以下是本時段重點（每檔一句話）：",
        f"時段：{window_label}",
        "",
    ]
    html_items: list[str] = []

    if not ranked:
        lines.append("本時段沒有需要特別注意的股票。")
        html_items.append("<p>本時段沒有需要特別注意的股票。</p>")
    else:
        for i, sym in enumerate(ranked, 1):
            name = names.get(sym, sym)
            what = summarize_stock(by_symbol[sym])
            line = f"{i}. {sym} {name}：{what}"
            lines.append(line)
            html_items.append(
                f"<li style='margin:8px 0'><b>{sym} {name}</b>：{what}</li>"
            )

    if extra_sections:
        for sec_title, sec_lines in extra_sections:
            lines.append("")
            lines.append(f"【{sec_title}】")
            lines.extend(sec_lines)

    lines.append("")
    lines.append(DISCLAIMER)
    text = "\n".join(lines)

    html = f"""
    <html><body style="font-family:Microsoft JhengHei,sans-serif;font-size:15px;color:#222">
    <p><b>{title}</b><br>時段：{window_label}</p>
    <p>以下是本時段重點（每檔一句話）：</p>
    <ol style="padding-left:1.2rem">
      {''.join(html_items) if ranked else '<p>本時段沒有需要特別注意的股票。</p>'}
    </ol>
    <p style="color:#888;font-size:12px">{DISCLAIMER}</p>
    </body></html>
    """
    return subject, text, html, included_ids
