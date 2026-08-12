"""Send a sample TW alert digest with fake data (preview format)."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from digest.format import build_digest_bodies
from mailer.smtp import send_mail, smtp_configured

TZ = ZoneInfo("Asia/Taipei")


def main() -> int:
    if not smtp_configured():
        print("SMTP not configured")
        return 1

    now = datetime.now(TZ)
    end_min = min(now.minute + 1, 59)
    window = f"{now.strftime('%H:%M')}–{now.replace(minute=end_min).strftime('%H:%M')}（假資料示範）"

    signals = [
        {
            "symbol": "2330",
            "category": "price_volume",
            "rule_id": "PX_VOL_UP",
            "score": 95,
            "payload": {
                "change_pct": 3.25,
                "vol_ratio": 2.8,
                "price": 985.0,
                "note": "上漲 3.25% 且量比 2.80x",
            },
        },
        {
            "symbol": "2454",
            "category": "price_volume",
            "rule_id": "PX_MOVE_5",
            "score": 88,
            "payload": {
                "change_pct": 5.12,
                "vol_ratio": 1.9,
                "price": 1285.0,
                "note": "漲跌幅 5.12% ≥ 5%",
            },
        },
        {
            "symbol": "2408",
            "category": "price_volume",
            "rule_id": "PX_MOVE_3",
            "score": 72,
            "payload": {
                "change_pct": 4.05,
                "vol_ratio": 3.1,
                "price": 68.5,
                "note": "漲跌幅 4.05% ≥ 3%",
            },
        },
        {
            "symbol": "2327",
            "category": "technical",
            "rule_id": "BREAK_MA20",
            "score": 68,
            "payload": {"change_pct": 2.1, "note": "收盤站上 MA20，RSI 62"},
        },
        {
            "symbol": "2382",
            "category": "price_volume",
            "rule_id": "VOL_SPIKE",
            "score": 75,
            "payload": {
                "change_pct": 2.85,
                "vol_ratio": 3.4,
                "price": 312.0,
                "note": "量比 3.40x（同時段均量）",
            },
        },
        {
            "symbol": "3711",
            "category": "institutional",
            "rule_id": "INST_FOREIGN_BIG",
            "score": 70,
            "payload": {"note": "外資買超 12,345,678 股"},
        },
        {
            "symbol": "ai_server",
            "category": "sector",
            "rule_id": "SECTOR_UP",
            "score": 82,
            "payload": {
                "sector_name": "AI 伺服器",
                "avg_change": 2.79,
                "breadth_up": 0.78,
                "hot": True,
                "note": "【AI 伺服器】族群平均上漲 2.79%，14/18 檔上漲；領漲 6669 緯穎 +4.20%",
            },
        },
        {
            "symbol": "memory",
            "category": "sector",
            "rule_id": "SECTOR_BREADTH_UP",
            "score": 78,
            "payload": {
                "sector_name": "記憶體",
                "avg_change": 1.95,
                "breadth_up": 0.86,
                "hot": True,
                "note": "【記憶體】多頭擴散 86% 成分股上漲（6/7）",
            },
        },
        {
            "symbol": "passive",
            "category": "sector",
            "rule_id": "SECTOR_UP",
            "score": 74,
            "payload": {
                "sector_name": "被動元件",
                "avg_change": 1.62,
                "breadth_up": 0.65,
                "hot": True,
                "note": "【被動元件】族群平均上漲 1.62%，61/94 檔上漲；領漲 2327 國巨 +2.10%",
            },
        },
    ]

    extra = [
        (
            "法人動向",
            [
                "2330 台積電：外資今日買超 8,520,000 股",
                "2454 聯發科：外資今日買超 3,210,000 股",
                "2408 南亞科：外資今日賣超 1,850,000 股",
            ],
        ),
        (
            "注意／處置／訊息",
            [
                "1234 某某電子：被列為注意股",
                "5678 範例科技：重大訊息：子公司取得重大訂單…",
            ],
        ),
    ]

    subject, text, html, _ = build_digest_bodies(
        title=f"{now.strftime('%H:%M')} digest",
        window_label=window,
        signals=signals,
        extra_sections=extra,
    )

    banner = "【此為範例信，以下數字與時段均為假資料，僅供預覽警示格式】\n\n"
    text = banner + text
    html = (
        '<p style="background:#fff3cd;padding:10px;border-radius:6px">'
        "<b>【範例信】</b> 以下為假資料，僅供預覽警示格式。</p>"
        + html
    )
    subject = subject.replace("[台股監控]", "[台股監控] 【範例】", 1)

    send_mail(subject, text, html)
    print(f"Sent TW: {subject}")

    # 美股範例信
    from digest.format import select_top_symbols, summarize_stock
    from digest.us_mail import DISCLAIMER as US_DISCLAIMER
    from us.watchlist import us_name

    us_signals = [
        {
            "symbol": "NVDA",
            "category": "us_price",
            "rule_id": "US_MOVE_5",
            "score": 90,
            "payload": {"change_pct": 5.8, "price": 875.2, "note": "US_MOVE_5"},
        },
        {
            "symbol": "TSM",
            "category": "us_price",
            "rule_id": "US_TW_LINK",
            "score": 85,
            "payload": {"change_pct": 3.2, "price": 168.5, "note": "US_TW_LINK"},
        },
        {
            "symbol": "SOXX",
            "category": "us_price",
            "rule_id": "US_MOVE_3",
            "score": 72,
            "payload": {"change_pct": 2.4, "price": 245.1, "note": "US_MOVE_3"},
        },
        {
            "symbol": "ai_semi",
            "category": "us_sector",
            "rule_id": "SECTOR_UP",
            "score": 82,
            "payload": {
                "sector_name": "AI／龍頭半導體",
                "avg_change": 3.15,
                "breadth_up": 1.0,
                "hot": True,
                "note": "【AI／龍頭半導體】族群平均上漲 3.15%，4/4 檔上漲；領漲 NVDA 輝達 +5.80%",
            },
        },
        {
            "symbol": "semi_etf",
            "category": "us_sector",
            "rule_id": "SECTOR_BREADTH_UP",
            "score": 75,
            "payload": {
                "sector_name": "半導體 ETF",
                "avg_change": 2.1,
                "breadth_up": 1.0,
                "hot": True,
                "note": "【半導體 ETF】多頭擴散 100% 成分股上漲（2/2）",
            },
        },
    ]
    from digest.format import build_sector_section_lines
    from us.sectors import US_SECTOR_LABEL

    ranked, by_symbol, _ = select_top_symbols(us_signals, top_n=3)
    sector_lines = build_sector_section_lines(
        us_signals, top_n=5, category="us_sector", label_map=US_SECTOR_LABEL
    )
    us_lines = [
        "【此為範例信，以下數字均為假資料，僅供預覽警示格式】",
        "",
        "以下是本時段重點（每檔一句話）：",
        "時段：22:05–23:05 (台北)（假資料示範）",
        "",
    ]
    us_html_items = []
    for i, sym in enumerate(ranked, 1):
        name = us_name(sym)
        what = summarize_stock(by_symbol[sym])
        us_lines.append(f"{i}. {sym} {name}：{what}")
        us_html_items.append(f"<li style='margin:8px 0'><b>{sym} {name}</b>：{what}</li>")
    if sector_lines:
        us_lines.append("")
        us_lines.append("【題材族群】")
        us_lines.extend(sector_lines)
    us_lines.extend(["", US_DISCLAIMER])
    us_subject = f"[美股監控] 【範例】美股 22:05 digest｜{len(ranked)} 檔重點"
    us_text = "\n".join(us_lines)
    us_html = f"""
    <html><body style="font-family:Microsoft JhengHei,sans-serif;font-size:15px;color:#222">
    <p style="background:#fff3cd;padding:10px;border-radius:6px"><b>【範例信】</b> 以下為假資料，僅供預覽警示格式。</p>
    <p><b>【範例】美股 22:05 digest</b><br>時段：22:05–23:05 (台北)（假資料示範）</p>
    <p>以下是本時段重點（每檔一句話）：</p>
    <ol style="padding-left:1.2rem">{''.join(us_html_items)}</ol>
    {f"<p><b>【題材族群】</b></p><ul>{''.join(f'<li>{l}</li>' for l in sector_lines)}</ul>" if sector_lines else ""}
    <p style="color:#888;font-size:12px">{US_DISCLAIMER}</p>
    </body></html>
    """
    send_mail(us_subject, us_text, us_html)
    print(f"Sent US: {us_subject}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
