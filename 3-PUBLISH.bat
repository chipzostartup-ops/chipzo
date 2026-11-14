@echo off
setlocal
cd /d "%~dp0"
title Chipzo - Publish
color 0B

echo.
echo  ============================================
echo   CHIPZO  -  PUBLISH WHAT IS DUE
echo  ============================================
echo.
echo  Step 1/3  regenerating platform files...
echo.

py -3 --version >nul 2>nul
if errorlevel 1 goto noPython

py -3 automation\repurpose.py --all
echo.
echo  Step 2/3  updating the schedule...
echo.
py -3 automation\queue.py build
echo.
echo  Step 3/3  publishing...
echo.
py -3 automation\run_daily.py
goto done

:noPython
echo  [!] Python not found. Install from python.org and tick "Add to PATH".

:done
echo.
echo  Opening the dashboard...
py -3 automation\dashboard.py >nul 2>nul
if exist dashboard\index.html start "" dashboard\index.html
echo.
pause >nul
