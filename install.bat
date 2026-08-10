@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === 台股監控系統 - 安裝 ===
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [錯誤] 找不到 python，請先安裝 Python 3.11+ 並勾選 Add to PATH。
  pause
  exit /b 1
)

echo [1/3] 建立虛擬環境 .venv ...
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 (
    echo [錯誤] 建立虛擬環境失敗。
    pause
    exit /b 1
  )
) else (
  echo       .venv 已存在，略過建立。
)

echo [2/3] 安裝依賴套件 ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [錯誤] pip install 失敗。
  pause
  exit /b 1
)

echo [3/3] 準備 .env 設定檔 ...
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo       已從 .env.example 複製為 .env
  echo.
  echo *** 請用記事本編輯 .env，填入 Email / SMTP 資訊後再執行 run.bat ***
  echo     檔案位置：%~dp0.env
  echo.
  notepad ".env"
) else (
  echo       .env 已存在，未覆蓋。
)

echo.
echo [完成] 安裝結束。
echo 下一步：確認 .env 裡的 SMTP 設定，然後雙擊 run.bat 啟動。
echo.
pause
