"""Map every TWSE symbol to a theme sector (題材族群).

Based on TWSE industry codes (產業別) plus symbol overrides for finer splits
within electronics — aligned with 2025–2026 hot themes: AI server, memory/HBM,
passive components, panels, PCB/ABF, etc.
"""

from __future__ import annotations

from typing import Optional

# TWSE 產業別代碼 → 中文名稱（證交所 ISIN 分類，2024 修訂後）
INDUSTRY_NAME: dict[str, str] = {
    "01": "水泥工業",
    "02": "食品工業",
    "03": "塑膠工業",
    "04": "紡織纖維",
    "05": "電機機械",
    "06": "電器電纜",
    "08": "玻璃陶瓷",
    "09": "造紙工業",
    "10": "鋼鐵工業",
    "11": "橡膠工業",
    "12": "汽車工業",
    "13": "電子工業",
    "14": "建材營造",
    "15": "航運業",
    "16": "觀光餐旅",
    "17": "金融保險",
    "18": "貿易百貨",
    "19": "綜合",
    "20": "其他",
    "21": "化學工業",
    "22": "生技醫療",
    "23": "油電燃氣",
    "24": "半導體業",
    "25": "電腦週邊",
    "26": "光電業",
    "27": "通信網路",
    "28": "電子零組件",
    "29": "電子通路",
    "30": "資訊服務",
    "31": "其他電子",
    "32": "文化創意",
    "33": "農業科技",
    "35": "綠能環保",
    "36": "數位雲端",
    "37": "運動休閒",
    "38": "居家生活",
    "91": "存託憑證",
}

# 題材族群代碼 → 顯示名稱
SECTOR_LABEL: dict[str, str] = {
    "memory": "記憶體",
    "ic_design": "IC 設計",
    "semi": "半導體製造",
    "osat": "封測",
    "panel": "面板",
    "passive": "被動元件",
    "pcb": "PCB／載板",
    "ai_server": "AI 伺服器",
    "pc_oem": "電腦週邊",
    "network": "通信網通",
    "e_dist": "電子通路",
    "other_elec": "其他電子",
    "finance": "金融保險",
    "shipping": "航運",
    "construction": "營建",
    "biotech": "生技醫療",
    "green": "綠能環保",
    "digital": "數位雲端",
    "consumer": "消費生活",
    "traditional": "傳統產業",
    "other": "其他",
}

# 2025–2026 市場關注度較高的題材（用於 UI 排序與 digest 優先）
HOT_SECTORS: frozenset[str] = frozenset(
    {
        "memory",
        "ai_server",
        "passive",
        "pcb",
        "semi",
        "osat",
        "panel",
        "ic_design",
        "network",
    }
)

# TWSE 產業別 → 預設題材族群
INDUSTRY_DEFAULT_SECTOR: dict[str, str] = {
    "01": "traditional",
    "02": "traditional",
    "03": "traditional",
    "04": "traditional",
    "05": "traditional",
    "06": "traditional",
    "08": "traditional",
    "09": "traditional",
    "10": "traditional",
    "11": "traditional",
    "12": "traditional",
    "13": "other_elec",
    "14": "construction",
    "15": "shipping",
    "16": "consumer",
    "17": "finance",
    "18": "consumer",
    "19": "traditional",
    "20": "other",
    "21": "traditional",
    "22": "biotech",
    "23": "traditional",
    "24": "semi",
    "25": "pc_oem",
    "26": "panel",
    "27": "network",
    "28": "passive",
    "29": "e_dist",
    "30": "digital",
    "31": "other_elec",
    "32": "consumer",
    "33": "traditional",
    "35": "green",
    "36": "digital",
    "37": "consumer",
    "38": "consumer",
    "91": "other",
}

# 個股覆寫（細分半導體／零組件等）
SYMBOL_SECTOR: dict[str, str] = {
    # --- 記憶體（DRAM / NAND / 模組）---
    "2408": "memory",
    "2344": "memory",
    "3006": "memory",
    "4967": "memory",
    "3260": "memory",
    "8271": "memory",
    "3581": "memory",
    "5351": "memory",
    "2337": "memory",
    "6485": "memory",
    "8299": "memory",
    "5521": "memory",
    # --- IC 設計 ---
    "2454": "ic_design",
    "3034": "ic_design",
    "2379": "ic_design",
    "3443": "ic_design",
    "3661": "ic_design",
    "3035": "ic_design",
    "4919": "ic_design",
    "8016": "ic_design",
    "5269": "ic_design",
    "6525": "ic_design",
    "6415": "ic_design",
    "5274": "ic_design",
    "4961": "ic_design",
    "2401": "ic_design",
    "2436": "ic_design",
    "2481": "ic_design",
    "3041": "ic_design",
    "3532": "ic_design",
    "3545": "ic_design",
    "3665": "ic_design",
    "6104": "ic_design",
    "6223": "ic_design",
    "6443": "ic_design",
    "6531": "ic_design",
    "6741": "ic_design",
    "6756": "ic_design",
    "6789": "ic_design",
    # --- 封測 ---
    "3711": "osat",
    "6239": "osat",
    "2449": "osat",
    "6510": "osat",
    "3264": "osat",
    "8150": "osat",
    "5347": "osat",
    "3374": "osat",
    "6271": "osat",
    "6451": "osat",
    # --- 半導體製造（晶圓／特殊製程，非 IC 設計）---
    "2330": "semi",
    "2303": "semi",
    "6770": "semi",
    "6488": "semi",
    "6182": "semi",
    "3105": "semi",
    "3680": "semi",
    # --- 被動元件（MLCC / 電感 / 電阻）---
    "2327": "passive",
    "2492": "passive",
    "6173": "passive",
    "3016": "passive",
    "6191": "passive",
    "2428": "passive",
    "2476": "passive",
    "2484": "passive",
    "8096": "passive",
    "8358": "passive",
    # --- PCB / 載板 ---
    "3037": "pcb",
    "3189": "pcb",
    "6213": "pcb",
    "6153": "pcb",
    "2383": "pcb",
    "2367": "pcb",
    "4958": "pcb",
    "8046": "pcb",
    "6274": "pcb",
    "5469": "pcb",
    "3515": "pcb",
    "6196": "pcb",
    "6412": "pcb",
    "6558": "pcb",
    # --- AI 伺服器 / 液冷 / 代工 ---
    "2382": "ai_server",
    "3231": "ai_server",
    "6669": "ai_server",
    "3017": "ai_server",
    "2368": "ai_server",
    "6665": "ai_server",
    "2317": "ai_server",
    "2356": "ai_server",
    "2357": "ai_server",
    "2324": "ai_server",
    "2301": "ai_server",
    "2353": "ai_server",
    "2352": "ai_server",
    "3324": "ai_server",
    "3653": "ai_server",
    "3665": "ai_server",
    "6414": "ai_server",
    "8210": "ai_server",
    "4938": "ai_server",
    "2395": "ai_server",
    "3706": "ai_server",
    "6668": "ai_server",
    "6664": "ai_server",
}

# 名稱關鍵字（產業別無法細分時的補充）
_NAME_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("記憶體", "memory"),
    ("DRAM", "memory"),
    ("快閃", "memory"),
    ("被動", "passive"),
    ("電容", "passive"),
    ("電感", "passive"),
    ("MLCC", "passive"),
    ("面板", "panel"),
    ("顯示", "panel"),
    ("載板", "pcb"),
    ("印刷電路", "pcb"),
    ("伺服器", "ai_server"),
    ("液冷", "ai_server"),
    ("散熱", "ai_server"),
)


def industry_label(code: Optional[str]) -> str:
    if not code:
        return "未知"
    key = str(code).strip().zfill(2) if str(code).strip().isdigit() else str(code).strip()
    return INDUSTRY_NAME.get(key, f"產業{key}")


def classify_symbol(
    symbol: str,
    industry: Optional[str] = None,
    name: Optional[str] = None,
) -> str:
    """Return theme sector code for a listed symbol."""
    sym = str(symbol or "").strip()
    if sym in SYMBOL_SECTOR:
        return SYMBOL_SECTOR[sym]

    nm = str(name or "")
    for kw, sector in _NAME_KEYWORDS:
        if kw in nm:
            return sector

    ind = str(industry or "").strip()
    if ind.isdigit():
        ind = ind.zfill(2)
    return INDUSTRY_DEFAULT_SECTOR.get(ind, "other")


def get_sector_for_symbol(
    symbol: str,
    industries: dict[str, str],
    names: dict[str, str],
) -> str:
    return classify_symbol(
        symbol,
        industries.get(symbol),
        names.get(symbol),
    )


def list_sectors() -> list[tuple[str, str, bool]]:
    """All sectors sorted: hot themes first, then by label."""
    items = [(code, SECTOR_LABEL.get(code, code), code in HOT_SECTORS) for code in SECTOR_LABEL]
    items.sort(key=lambda x: (not x[2], x[1]))
    return items
