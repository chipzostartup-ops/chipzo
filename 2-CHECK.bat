@echo off
setlocal
cd /d "%~dp0"
title Chipzo - Status
color 0B

echo.
echo  ============================================
echo   CHIPZO  -  WHAT IS CONNECTED
echo  ============================================
echo.

py -3 --version >nul 2>nul
if not errorlevel 1 (
    py -3 automation\connect.py --check
    goto done
)
python --version >nul 2>nul
if not errorlevel 1 (
    python automation\connect.py --check
    goto done
)
echo  [!] Python not found.

:done
echo.
pause >nul
