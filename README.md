# 台股／美股監控告警系統

- **台股**：上市股每分鐘 MIS 快照，價量／技術／法人／事件訊號，盤中整點 + 盤後日結 Email  
- **美股**：只盯與台股相關的指數／ETF／個股（Yahoo），**獨立**寄送 `[美股監控]` 信件  

> 公開資料有延遲。產出僅供監控參考，**非投資建議**。

## 美股觀察清單

SOXX、SMH、QQQ、SPY、TSM、NVDA、AMD、AVGO、ASML、AMAT、LRCX、KLAC、MU、INTC

- 盤中：美東時間每 2 分鐘擷取；每小時 digest（10:05–16:05 ET）  
- 盤後：美東 16:20 日結信  

## 安裝（Windows）

1. 雙擊 `install.bat`  
2. 編輯 `.env` 填 SMTP  
3. 雙擊 `run.bat`（**背景**執行台股+美股排程；用 `stop.bat` 停止）  
4. 雙擊 `dashboard.bat` → 上方切換「台股／美股」  
   - 需要看即時 log 時改用 `run-fg.bat`（前台視窗）

## 常用指令

```bash
python main.py              # 常駐（台+美）
python main.py --once       # 台股跑一次
python main.py --us-once    # 美股跑一次
python main.py --dry-run-digest hourly
python main.py --dry-run-digest us_hourly
python main.py --dry-run-digest us_eod
python main.py --test-mail
```

## Email

| 主旨前綴 | 內容 |
|----------|------|
| `[台股監控]` | 上市股 digest／日結 |
| `[美股監控]` | 與台股相關美股 digest／日結 |

SMTP 設定在專案根目錄 `.env`（見 `.env.example`）。

## 免責

公開資料不保證即時與正確；投資請自行負責。
