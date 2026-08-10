"""Local Streamlit dashboard — Cathay-inspired cards for TW + US."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components

from config import TZ_NAME, cfg
from db import store
from digest.format import CATEGORY_LABEL, select_top_symbols
from ingest.mis import is_trading_session
from ingest.us_yahoo import is_us_trading_session
from us.watchlist import US_WATCHLIST, us_name

TZ = ZoneInfo(TZ_NAME)

TEAL = "#00A99D"
TEAL_DARK = "#008F85"
BG = "#F5F5F5"
CARD_HDR = "#EEEEEE"
UP = "#E53935"
DOWN = "#2E7D32"
FLAT = "#757575"

TW_RULES = [
    ("PX_MOVE_3", "漲跌幅 ≥ 3%"),
    ("PX_MOVE_5", "漲跌幅 ≥ 5%"),
    ("VOL_SPIKE", "量比 ≥ 2.5"),
    ("PX_VOL_UP / DOWN", "價量同向"),
    ("BREAK_MA20/60", "均線突破"),
    ("法人／事件", "盤後為主"),
]
US_RULES = [
    ("US_MOVE_3", "ETF≥2%／個股≥3%"),
    ("US_MOVE_5", "ETF≥3.5%／個股≥5%"),
    ("US_TW_LINK", "TSM/SOXX/SMH/NVDA ≥2%"),
]

SHELL_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');
html, body, [class*="css"] {{ font-family: "Noto Sans TC", "Microsoft JhengHei", sans-serif; }}
.stApp {{ background: {BG}; }}
.block-container {{ padding-top: 0.6rem !important; padding-bottom: 2rem !important; max-width: 720px; }}
#MainMenu, footer, [data-testid="stToolbar"], div[data-testid="stDecoration"] {{ display: none; }}
header {{ visibility: hidden; }}
.app-top {{
  background: #fff; margin: -0.6rem -1rem 0.8rem; padding: 14px 16px 0;
  border-bottom: 1px solid #e5e5e5;
}}
.app-title {{ text-align: center; font-size: 1.15rem; font-weight: 700; color: #222; margin: 0 0 10px; }}
.metrics-row {{
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 8px 0 12px;
}}
.m-chip {{
  background: #fff; border-radius: 10px; padding: 8px 10px; text-align: center;
  border: 1px solid #ebebeb;
}}
.m-chip .k {{ font-size: 0.72rem; color: #888; }}
.m-chip .v {{ font-size: 0.92rem; font-weight: 700; color: #222; margin-top: 2px; }}
.section-h {{ font-size: 0.95rem; font-weight: 700; color: #333; margin: 14px 0 8px; }}
.hint {{ font-size: 0.78rem; color: #999; margin: 0 0 8px; }}
</style>
"""


def _tone(change_pct) -> str:
    if change_pct is None:
        return "flat"
    if change_pct > 0:
        return "up"
    if change_pct < 0:
        return "down"
    return "flat"


def _color(tone: str) -> str:
    return {"up": UP, "down": DOWN, "flat": FLAT}[tone]


def _fmt_price(price) -> str:
    if price is None:
        return "—"
    if isinstance(price, (int, float)):
        s = f"{price:,.2f}".rstrip("0").rstrip(".")
        return s or "0"
    return str(price)


def _fmt_diff(change_pct, price, prev_close) -> tuple[str, str]:
    if change_pct is None:
        return "—", "—"
    abs_chg = None
    if price is not None and prev_close not in (None, 0):
        abs_chg = float(price) - float(prev_close)
    elif price is not None:
        try:
            prev = float(price) / (1 + float(change_pct) / 100.0)
            abs_chg = float(price) - prev
        except ZeroDivisionError:
            abs_chg = None
    pct = f"{abs(float(change_pct)):.2f}%"
    diff = "—" if abs_chg is None else (f"{abs(abs_chg):.2f}".rstrip("0").rstrip(".") or "0")
    return diff, pct


def _arrow(tone: str) -> str:
    return {"up": "▲", "down": "▼", "flat": "–"}[tone]


def _cards_html(items: list[dict]) -> str:
    """items: symbol, name, rank, score, price, change, prev, cats, note, border_color"""
    cards = []
    for it in items:
        tone = _tone(it.get("change"))
        color = it.get("border_color") or _color(tone)
        diff, pct = _fmt_diff(it.get("change"), it.get("price"), it.get("prev"))
        title = f"{it['name']} {it['symbol']}"
        cards.append(
            f"""
            <div class="card" style="border-color:{color}">
              <div class="card-h">
                <span class="nm">{escape(title)}</span>
                <span class="rk">#{it['rank']} · Score {it['score']:.0f}</span>
              </div>
              <div class="card-b">
                <div class="price" style="color:{color}">
                  <span class="hash">#</span>{escape(_fmt_price(it.get('price')))}
                </div>
                <div class="chg" style="color:{color}">
                  <span>{escape(diff)} {_arrow(tone)}</span>
                  <span>{escape(pct)}</span>
                </div>
                <div class="foot">{escape(it.get('cats') or '')}</div>
                <div class="note">{escape(str(it.get('note') or '')[:52])}</div>
              </div>
            </div>
            """
        )
    return f"""
    <style>
      * {{ box-sizing: border-box; font-family: "Noto Sans TC", "Microsoft JhengHei", sans-serif; }}
      body {{ margin: 0; background: {BG}; }}
      .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 2px; }}
      .card {{ background: #fff; border: 1.5px solid {FLAT}; border-radius: 6px; overflow: hidden; }}
      .card-h {{ background: {CARD_HDR}; padding: 8px; text-align: center; border-bottom: 1px solid #e0e0e0; }}
      .card-h .nm {{ display: block; font-size: 14px; font-weight: 700; color: #222; }}
      .card-h .rk {{ display: block; font-size: 11px; color: #888; margin-top: 2px; }}
      .card-b {{ padding: 10px; }}
      .price {{ font-size: 28px; font-weight: 700; text-align: center; line-height: 1.15; }}
      .price .hash {{ font-size: 18px; margin-right: 2px; }}
      .chg {{ display: flex; justify-content: space-between; font-size: 13px; font-weight: 600; margin-top: 10px; padding: 0 4px; }}
      .foot {{ margin-top: 8px; font-size: 11px; color: {TEAL_DARK}; text-align: center; font-weight: 600; }}
      .note {{ margin-top: 4px; font-size: 11px; color: #777; text-align: center; }}
    </style>
    <div class="grid">{"".join(cards)}</div>
    """


def _watch_grid_html(bars: list[dict], names: dict[str, str]) -> str:
    """All watchlist quotes as Cathay cards (no score required)."""
    items = []
    ordered = sorted(bars, key=lambda b: abs(b.get("change_pct") or 0), reverse=True)
    for i, b in enumerate(ordered, 1):
        sym = b["symbol"]
        items.append(
            {
                "symbol": sym,
                "name": names.get(sym, sym),
                "rank": i,
                "score": abs(b.get("change_pct") or 0) * 10,
                "price": b.get("price"),
                "change": b.get("change_pct"),
                "prev": b.get("prev_close"),
                "cats": "美股連動" if sym in US_WATCHLIST else "",
                "note": "",
            }
        )
    return _cards_html(items)


st.set_page_config(page_title="行情 · 台股／美股", page_icon="📊", layout="centered")
st.markdown(SHELL_CSS, unsafe_allow_html=True)

st.markdown(
    '<div class="app-top"><div class="app-title">行情</div></div>',
    unsafe_allow_html=True,
)

market = st.radio(
    "市場",
    options=["台股", "美股"],
    horizontal=True,
    label_visibility="collapsed",
)

with st.sidebar:
    st.markdown("**設定**")
    auto = st.toggle("自動刷新", value=True)
    interval = st.slider("刷新間隔（秒）", 10, 120, 30, 5)
    day = st.date_input("日期", value=date.today())
    pending_only = st.toggle("只看未入信", value=False)
    if st.button("立即重新整理"):
        st.rerun()
    st.caption("僅本機 · 非投資建議")
    if market == "美股":
        st.caption("美股信主旨：[美股監控]")
    else:
        st.caption("台股信主旨：[台股監控]")


@st.fragment(run_every=timedelta(seconds=interval) if auto else None)
def live_dashboard() -> None:
    store.init_db()
    now = datetime.now(TZ)

    if market == "台股":
        if not cfg.db_path.exists():
            st.error("找不到資料庫")
            return
        names = store.get_symbol_names()
        signals = store.signals_for_day(day, pending_only=pending_only)
        ranked, by_symbol, scores = select_top_symbols(signals, top_n=cfg.digest_top_n)
        latest_ts = store.latest_bar_ts()
        pending_n = sum(1 for s in signals if not s.get("included_in_digest_at"))
        status = "盤中" if is_trading_session(now) else "休市"

        st.markdown(
            f"""
            <div class="metrics-row">
              <div class="m-chip"><div class="k">台股</div><div class="v">{status}</div></div>
              <div class="m-chip"><div class="k">行情</div><div class="v">{(latest_ts or '—')[-8:] if latest_ts else '—'}</div></div>
              <div class="m-chip"><div class="k">未入信</div><div class="v">{pending_n}</div></div>
              <div class="m-chip"><div class="k">訊號</div><div class="v">{len(signals)}</div></div>
            </div>
            <p class="hint">更新 {now.strftime('%H:%M:%S')} · 紅漲綠跌 · Email Top {cfg.digest_top_n}</p>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="section-h">關注字卡 · Top {cfg.digest_top_n}</div>',
            unsafe_allow_html=True,
        )
        if not ranked:
            st.info("目前沒有台股訊號。")
        else:
            items = []
            for i, sym in enumerate(ranked, 1):
                rules = by_symbol[sym]
                bar = store.get_bar_for_symbol(sym) or {}
                payload = max(rules, key=lambda r: float(r.get("score") or 0)).get("payload") or {}
                cats = " · ".join(
                    sorted(
                        {
                            CATEGORY_LABEL.get(r.get("category") or "", "")
                            for r in rules
                        }
                    )
                )
                note = payload.get("note") or ""
                items.append(
                    {
                        "symbol": sym,
                        "name": names.get(sym, sym),
                        "rank": i,
                        "score": scores[sym],
                        "price": bar.get("price", payload.get("price")),
                        "change": bar.get("change_pct", payload.get("change_pct")),
                        "prev": bar.get("prev_close"),
                        "cats": cats,
                        "note": note,
                    }
                )
            rows = (len(items) + 1) // 2
            components.html(_cards_html(items), height=min(1200, max(320, rows * 168)), scrolling=True)

        with st.expander("台股規則", expanded=False):
            for a, b in TW_RULES:
                st.markdown(f"**{a}** — {b}")
        return

    # ---- US ----
    names = {s: us_name(s) for s in US_WATCHLIST}
    signals = store.us_signals_for_day(day, pending_only=pending_only)
    # US session may span Taipei calendar days — also show yesterday pending
    if day == date.today():
        yday = day - timedelta(days=1)
        extra = store.us_signals_for_day(yday, pending_only=pending_only)
        seen = {(s["symbol"], s["rule_id"], s["ts"]) for s in signals}
        for s in extra:
            key = (s["symbol"], s["rule_id"], s["ts"])
            if key not in seen:
                signals.append(s)

    ranked, by_symbol, scores = select_top_symbols(signals, top_n=min(cfg.digest_top_n, 14))
    bars = store.latest_us_bars()
    latest_ts = store.latest_us_bar_ts()
    pending_n = sum(1 for s in signals if not s.get("included_in_digest_at"))
    status = "盤中" if is_us_trading_session(now) else "休市"

    st.markdown(
        f"""
        <div class="metrics-row">
          <div class="m-chip"><div class="k">美股</div><div class="v">{status}</div></div>
          <div class="m-chip"><div class="k">行情</div><div class="v">{(latest_ts or '—')[-8:] if latest_ts else '—'}</div></div>
          <div class="m-chip"><div class="k">未入信</div><div class="v">{pending_n}</div></div>
          <div class="m-chip"><div class="k">標的</div><div class="v">{len(bars)}</div></div>
        </div>
        <p class="hint">更新 {now.strftime('%H:%M:%S')} · 與台股相關指數／個股 · 獨立 Email [美股監控]</p>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-h">觀察清單（全部）</div>', unsafe_allow_html=True)
    if not bars:
        st.info("尚無美股報價。可執行 `python main.py --us-once`，或等美股盤中由 run.bat 自動抓。")
    else:
        rows = (len(bars) + 1) // 2
        components.html(
            _watch_grid_html(bars, names),
            height=min(1400, max(320, rows * 168)),
            scrolling=True,
        )

    st.markdown('<div class="section-h">訊號關注字卡</div>', unsafe_allow_html=True)
    if not ranked:
        st.caption("目前無觸發訊號（門檻未到）。")
    else:
        items = []
        for i, sym in enumerate(ranked, 1):
            rules = by_symbol[sym]
            bar = store.get_us_bar(sym) or {}
            payload = max(rules, key=lambda r: float(r.get("score") or 0)).get("payload") or {}
            note = payload.get("note") or ""
            items.append(
                {
                    "symbol": sym,
                    "name": names.get(sym, us_name(sym)),
                    "rank": i,
                    "score": scores[sym],
                    "price": bar.get("price", payload.get("price")),
                    "change": bar.get("change_pct", payload.get("change_pct")),
                    "prev": bar.get("prev_close"),
                    "cats": "訊號",
                    "note": note,
                }
            )
        rows = (len(items) + 1) // 2
        components.html(_cards_html(items), height=min(800, max(280, rows * 168)), scrolling=True)

    with st.expander("美股規則", expanded=False):
        for a, b in US_RULES:
            st.markdown(f"**{a}** — {b}")
        st.caption("監控：" + "、".join(f"{k} {v[0]}" for k, v in US_WATCHLIST.items()))


live_dashboard()
