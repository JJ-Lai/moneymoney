@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === 停止背景監控 ===
echo.

if not exist "data\monitor.pid" (
  echo [提示] 找不到 data\monitor.pid，沒有記錄中的背景行程。
  pause
  exit /b 0
)

set /p PID=<data\monitor.pid
echo 嘗試停止 PID %PID% ...

taskkill /PID %PID% /F >nul 2>&1
if errorlevel 1 (
  echo [提示] 行程可能已結束，或無法停止。
) else (
  echo [成功] 已停止 PID %PID%。
)

del /f /q "data\monitor.pid" >nul 2>&1
echo.
pause
exit /b 0
