@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === 前台啟動（除錯用，可見日誌） ===
echo 按 Ctrl+C 可停止。
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [錯誤] 找不到虛擬環境，請先執行 install.bat。
  pause
  exit /b 1
)

".venv\Scripts\python.exe" main.py
pause
