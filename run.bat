@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === 台股／美股監控 - 背景啟動 ===
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [錯誤] 找不到虛擬環境，請先執行 install.bat。
  pause
  exit /b 1
)

if not exist ".env" (
  echo [錯誤] 找不到 .env，請先執行 install.bat 並填寫 Email 設定。
  pause
  exit /b 1
)

if not exist "data" mkdir data

if exist "data\monitor.pid" (
  set /p OLD_PID=<data\monitor.pid
  tasklist /FI "PID eq %OLD_PID%" 2>nul | find "%OLD_PID%" >nul
  if not errorlevel 1 (
    echo [提示] 監控已在背景執行中 ^(PID %OLD_PID%^)。
    echo 若要重啟，請先執行 stop.bat。
    pause
    exit /b 0
  )
)

powershell -NoProfile -Command ^
  "$p = Start-Process -FilePath '%cd%\.venv\Scripts\python.exe' -ArgumentList 'main.py' -WorkingDirectory '%cd%' -WindowStyle Hidden -RedirectStandardOutput '%cd%\data\monitor.out.log' -RedirectStandardError '%cd%\data\monitor.err.log' -PassThru; Set-Content -Path '%cd%\data\monitor.pid' -Value $p.Id -Encoding ascii; Write-Output $p.Id"

if errorlevel 1 (
  echo [錯誤] 背景啟動失敗。
  pause
  exit /b 1
)

set /p NEW_PID=<data\monitor.pid
echo [成功] 已在背景執行。
echo   PID  : %NEW_PID%
echo   日誌 : data\monitor.out.log / data\monitor.err.log
echo   停止 : 雙擊 stop.bat
echo.
pause
exit /b 0
