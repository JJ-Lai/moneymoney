@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === 測試 Email / .env 設定 ===
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [錯誤] 找不到虛擬環境，請先執行 install.bat。
  pause
  exit /b 1
)

if not exist ".env" (
  echo [錯誤] 找不到 .env，請先執行 install.bat 並填寫 SMTP。
  pause
  exit /b 1
)

".venv\Scripts\python.exe" main.py --test-mail
set EXITCODE=%ERRORLEVEL%

echo.
if "%EXITCODE%"=="0" (
  echo [成功] 測試信已寄出，請檢查 MAIL_TO 收件匣（含垃圾郵件）。
) else (
  echo [失敗] SMTP 設定可能有誤，請檢查 .env 的 SMTP_USER / SMTP_PASSWORD / MAIL_TO。
)
echo.
pause
exit /b %EXITCODE%
