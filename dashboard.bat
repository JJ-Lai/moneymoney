@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === 台股監控 · 本機儀表板 ===
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [錯誤] 找不到虛擬環境，請先執行 install.bat。
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -c "import streamlit" 1>nul 2>nul
if errorlevel 1 (
  echo [安裝] 正在安裝 streamlit ...
  ".venv\Scripts\python.exe" -m pip install "streamlit>=1.37"
  if errorlevel 1 (
    echo [錯誤] streamlit 安裝失敗。
    pause
    exit /b 1
  )
)

echo 瀏覽器將開啟 http://127.0.0.1:8501
echo 請保持此視窗開啟；關閉視窗即停止儀表板。
echo 監控擷取請另開 run.bat。
echo.

".venv\Scripts\python.exe" -m streamlit run dashboard.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
pause
