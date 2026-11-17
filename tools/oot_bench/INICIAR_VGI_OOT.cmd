@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0vgi_oot.py" menu
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    python "%~dp0vgi_oot.py" menu
  ) else (
    echo Python 3 nao encontrado. Instale Python 3.10+ e execute novamente.
  )
)
echo.
pause
