@echo off
setlocal
cd /d "%~dp0"
title Chipzo - Connect
color 0B

echo.
echo  ============================================
echo   CHIPZO  -  CONNECT A PLATFORM
echo  ============================================
echo.
echo  This connects Telegram, Blogger, Facebook,
echo  Instagram, WhatsApp or your email list.
echo.
echo  Start with option 1 (Telegram). It is free
echo  and takes about 5 minutes.
echo.

py -3 --version >nul 2>nul
if not errorlevel 1 (
    py -3 automation\connect.py
    goto done
)

python --version >nul 2>nul
if not errorlevel 1 (
    python automation\connect.py
    goto done
)

echo  [!] Python was not found on this computer.
echo.
echo  Install it from https://www.python.org/downloads/
echo  IMPORTANT: tick "Add python.exe to PATH" during install.
echo.

:done
echo.
echo  ============================================
echo   Window will stay open. Press any key to close.
echo  ============================================
pause >nul
