@echo off
setlocal EnableDelayedExpansion
title InsulinPump OS — Starting

for /f %%A in ('echo prompt $E ^| cmd') do set "ESC=%%A"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "CYAN=%ESC%[96m"
set "WHITE=%ESC%[97m"
set "DIM=%ESC%[90m"
set "RESET=%ESC%[0m"
set "BOLD=%ESC%[1m"

cls
echo.
echo %CYAN%%BOLD%  ==========================================%RESET%
echo %CYAN%%BOLD%      InsulinPump OS  —  Starting...%RESET%
echo %CYAN%%BOLD%  ==========================================%RESET%
echo.

cd /d "%~dp0"

:: Check Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%  Docker Desktop is not running. Starting it...%RESET%
    for %%P in (
        "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
        "%LocalAppData%\Programs\Docker\Docker\Docker Desktop.exe"
    ) do if exist "%%~P" start "" "%%~P"

    echo %DIM%  Please wait while Docker starts...%RESET%
    set /a W=0
    :wait_d
    timeout /t 5 /nobreak >nul
    set /a W+=5
    docker info >nul 2>&1
    if %ERRORLEVEL% EQU 0 goto :d_ok
    if !W! LSS 90 goto :wait_d
    echo %YELLOW%  Docker is taking a while. Please open Docker Desktop manually and try again.%RESET%
    pause & exit /b 1
)
:d_ok
echo %GREEN%  ✔  Docker is running.%RESET%

echo %WHITE%  Starting services...%RESET%
docker compose up -d >nul 2>&1
echo %GREEN%  ✔  Services started.%RESET%

echo %WHITE%  Waiting for app to be ready...%RESET%
set /a E=0
:wait_a
timeout /t 4 /nobreak >nul
set /a E+=4
powershell -Command "try{$r=(Invoke-WebRequest -Uri 'http://localhost:8501/_stcore/health' -UseBasicParsing -TimeoutSec 3).StatusCode;exit($r -ne 200)}catch{exit 1}" >nul 2>&1
if %ERRORLEVEL% EQU 0 goto :ready
if !E! LSS 60 goto :wait_a

:ready
echo %GREEN%  ✔  Ready!%RESET%
echo.
start "" "http://localhost:8501"
echo %CYAN%  Browser opened: http://localhost:8501%RESET%
echo.
echo %DIM%  You can close this window. The system keeps running in the background.%RESET%
echo.
timeout /t 5 /nobreak >nul
