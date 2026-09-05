@echo off
title InsulinPump OS — Stopping

for /f %%A in ('echo prompt $E ^| cmd') do set "ESC=%%A"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "CYAN=%ESC%[96m"
set "DIM=%ESC%[90m"
set "RESET=%ESC%[0m"
set "BOLD=%ESC%[1m"

cls
echo.
echo %CYAN%%BOLD%  ==========================================%RESET%
echo %CYAN%%BOLD%      InsulinPump OS  —  Stopping...%RESET%
echo %CYAN%%BOLD%  ==========================================%RESET%
echo.

cd /d "%~dp0"

docker compose down >nul 2>&1
echo %GREEN%  ✔  InsulinPump OS has been stopped safely.%RESET%
echo.
echo %DIM%  All patient data is saved. Run start.bat to restart anytime.%RESET%
echo.
timeout /t 4 /nobreak >nul
