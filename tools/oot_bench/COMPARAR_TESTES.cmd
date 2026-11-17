@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0vgi_oot.py" compare
) else (
  python "%~dp0vgi_oot.py" compare
)
echo.
pause
