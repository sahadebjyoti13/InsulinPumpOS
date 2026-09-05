@echo off
setlocal EnableDelayedExpansion
title InsulinPump OS — First Time Setup

:: ============================================================
::  InsulinPump OS — One-Click Installer for Windows
::  Run this ONCE. It handles WSL2, Docker, and the full stack.
::  If a restart is needed, it resumes automatically after reboot.
:: ============================================================

set "APP_URL=http://localhost:8501"
set "MAX_WAIT=120"
set "RESUME_KEY=HKCU\Software\InsulinPumpOS"
set "SCRIPT_PATH=%~f0"

:: ── ANSI colours ─────────────────────────────────────────────
for /f %%A in ('echo prompt $E ^| cmd') do set "ESC=%%A"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "RED=%ESC%[91m"
set "CYAN=%ESC%[96m"
set "WHITE=%ESC%[97m"
set "DIM=%ESC%[90m"
set "RESET=%ESC%[0m"
set "BOLD=%ESC%[1m"

:: ── Check if we are resuming after a restart ─────────────────
set "RESUME_STEP="
for /f "tokens=3" %%V in ('reg query "%RESUME_KEY%" /v ResumeStep 2^>nul') do set "RESUME_STEP=%%V"

if defined RESUME_STEP (
    reg delete "%RESUME_KEY%" /v ResumeStep /f >nul 2>&1
    if "!RESUME_STEP!"=="step2" goto :step2
    if "!RESUME_STEP!"=="step3" goto :step3
)

cls
echo.
echo %CYAN%%BOLD%  ====================================================%RESET%
echo %CYAN%%BOLD%       InsulinPump OS  ---  First Time Setup%RESET%
echo %CYAN%%BOLD%  ====================================================%RESET%
echo.
echo %DIM%  This installer sets up everything automatically.%RESET%
echo %DIM%  You only need to run this once.%RESET%
echo.

:: ── Require Administrator ────────────────────────────────────
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%  Requesting administrator permission...%RESET%
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs"
    exit /b
)

:: ════════════════════════════════════════════════════════════
::  STEP 1 — WSL2
:: ════════════════════════════════════════════════════════════
echo %WHITE%%BOLD%  [Step 1/5]  Windows Subsystem for Linux (WSL2)%RESET%

wsl --status >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo %GREEN%  OK  WSL2 is already installed.%RESET%
    goto :step2
)

echo %DIM%  Installing WSL2 (takes 2-3 minutes)...%RESET%
wsl --install --no-distribution >nul 2>&1

if %ERRORLEVEL% EQU 0 (
    echo %GREEN%  OK  WSL2 installed.%RESET%
    echo.
    echo %YELLOW%  Your computer will restart now to finish WSL2 setup.%RESET%
    echo %YELLOW%  The installer will RESUME AUTOMATICALLY after restart.%RESET%
    echo %YELLOW%  You do not need to do anything after restarting.%RESET%
    echo.
    :: Save resume point in registry so we auto-continue after reboot
    reg add "%RESUME_KEY%" /v ResumeStep /t REG_SZ /d step2 /f >nul
    :: Add this script to startup so it runs after reboot
    reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\RunOnce" /v InsulinPumpOSResume /t REG_SZ /d "cmd /c \"%SCRIPT_PATH%\"" /f >nul
    echo %DIM%  Restarting in 10 seconds...%RESET%
    timeout /t 10 /nobreak >nul
    shutdown /r /t 0
    exit /b
) else (
    echo %YELLOW%  Could not install WSL2 automatically.%RESET%
    echo %WHITE%  Please do this manually:%RESET%
    echo %WHITE%  1. Open PowerShell as Administrator%RESET%
    echo %WHITE%  2. Run:  wsl --install%RESET%
    echo %WHITE%  3. Restart your computer%RESET%
    echo %WHITE%  4. Run install.bat again%RESET%
    pause
    exit /b 1
)

:: ════════════════════════════════════════════════════════════
::  STEP 2 — Docker Desktop
:: ════════════════════════════════════════════════════════════
:step2
cls
echo.
echo %CYAN%%BOLD%  ====================================================%RESET%
echo %CYAN%%BOLD%       InsulinPump OS  ---  First Time Setup%RESET%
echo %CYAN%%BOLD%  ====================================================%RESET%
echo.
echo %GREEN%  OK  WSL2 ready.%RESET%
echo.
echo %WHITE%%BOLD%  [Step 2/5]  Docker Desktop%RESET%

where docker >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo %GREEN%  OK  Docker is already installed.%RESET%
    goto :step3
)

echo %DIM%  Docker is not installed. Looking for installer...%RESET%

if exist "%~dp0Docker Desktop Installer.exe" (
    echo %DIM%  Found Docker installer. Running it now...%RESET%
    echo.
    echo %YELLOW%  Please click through the Docker installer.%RESET%
    echo %YELLOW%  When it finishes, press any key here to continue.%RESET%
    start /wait "" "%~dp0Docker Desktop Installer.exe"
    pause
    goto :verify_docker
)

echo %DIM%  Downloading Docker Desktop (~600 MB)...%RESET%
powershell -Command "& { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker Desktop Installer.exe' -OutFile '%~dp0Docker Desktop Installer.exe' -UseBasicParsing }" 2>nul

if %ERRORLEVEL% EQU 0 (
    echo %GREEN%  OK  Download complete.%RESET%
    echo %YELLOW%  Please click through the Docker installer.%RESET%
    echo %YELLOW%  When it finishes, press any key here to continue.%RESET%
    start /wait "" "%~dp0Docker Desktop Installer.exe"
    pause
    goto :verify_docker
) else (
    echo %RED%  Could not download Docker automatically.%RESET%
    echo %WHITE%  Please download from: https://www.docker.com/products/docker-desktop%RESET%
    echo %WHITE%  Then run this installer again.%RESET%
    pause
    exit /b 1
)

:verify_docker
where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo %RED%  Docker not detected after install.%RESET%
    echo %YELLOW%  Please restart your computer and run install.bat again.%RESET%
    pause
    exit /b 1
)
echo %GREEN%  OK  Docker installed.%RESET%

:: ════════════════════════════════════════════════════════════
::  STEP 3 — Start Docker Desktop engine
:: ════════════════════════════════════════════════════════════
:step3
echo.
echo %WHITE%%BOLD%  [Step 3/5]  Starting Docker Desktop%RESET%

docker info >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo %GREEN%  OK  Docker Desktop is already running.%RESET%
    goto :step4
)

echo %DIM%  Starting Docker Desktop...%RESET%

set "DOCKER_EXE="
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
if exist "%LocalAppData%\Programs\Docker\Docker\Docker Desktop.exe" set "DOCKER_EXE=%LocalAppData%\Programs\Docker\Docker\Docker Desktop.exe"

if defined DOCKER_EXE (
    start "" "%DOCKER_EXE%"
) else (
    echo %YELLOW%  Please open Docker Desktop from the Start menu, then press any key.%RESET%
    pause
)

echo %DIM%  Waiting for Docker engine (up to 90 seconds)...%RESET%
set /a WAITED=0
:wait_docker
timeout /t 5 /nobreak >nul
set /a WAITED+=5
docker info >nul 2>&1
if %ERRORLEVEL% EQU 0 goto :docker_ready
if !WAITED! LSS 90 (
    <nul set /p "=."
    goto :wait_docker
)
echo.
echo %RED%  Docker Desktop did not start in time.%RESET%
echo %YELLOW%  Please open Docker Desktop manually, wait for the green icon, then run install.bat again.%RESET%
pause
exit /b 1

:docker_ready
echo.
echo %GREEN%  OK  Docker Desktop is running.%RESET%

:: ════════════════════════════════════════════════════════════
::  STEP 4 — Start all services
:: ════════════════════════════════════════════════════════════
:step4
echo.
echo %WHITE%%BOLD%  [Step 4/5]  Starting InsulinPump OS Services%RESET%
echo %DIM%  Downloading components on first run (~300 MB). Please wait...%RESET%
echo.

cd /d "%~dp0"
docker compose pull 2>&1 | findstr /i "pulling downloaded error failed"
docker compose up -d --build >nul 2>&1

if %ERRORLEVEL% NEQ 0 (
    echo %RED%  Failed to start services:%RESET%
    docker compose up -d --build
    echo.
    echo %YELLOW%  Please show this error to your IT administrator.%RESET%
    pause
    exit /b 1
)
echo %GREEN%  OK  All services running.%RESET%

:: ════════════════════════════════════════════════════════════
::  STEP 5 — Wait for app and open browser
:: ════════════════════════════════════════════════════════════
:step5
echo.
echo %WHITE%%BOLD%  [Step 5/5]  Opening InsulinPump OS%RESET%
echo %DIM%  Waiting for app to be ready...%RESET%

set /a ELAPSED=0
:wait_app
timeout /t 4 /nobreak >nul
set /a ELAPSED+=4
powershell -Command "try{$r=(Invoke-WebRequest -Uri 'http://localhost:8501/_stcore/health' -UseBasicParsing -TimeoutSec 3).StatusCode;exit($r -ne 200)}catch{exit 1}" >nul 2>&1
if %ERRORLEVEL% EQU 0 goto :app_ready
if !ELAPSED! LSS %MAX_WAIT% (
    <nul set /p "=."
    goto :wait_app
)
echo.
echo %YELLOW%  App is taking longer than expected. Opening browser anyway...%RESET%
goto :open_browser

:app_ready
echo.
echo %GREEN%  OK  Application is ready!%RESET%

:open_browser
start "" "%APP_URL%"

echo.
echo %CYAN%%BOLD%  ====================================================%RESET%
echo %GREEN%%BOLD%       InsulinPump OS is live!%RESET%
echo %CYAN%%BOLD%  ====================================================%RESET%
echo.
echo %WHITE%  Browser opened to: %CYAN%%APP_URL%%RESET%
echo.
echo %DIM%  From tomorrow onwards:%RESET%
echo %DIM%    Start  ->  double-click  start.bat%RESET%
echo %DIM%    Stop   ->  double-click  stop.bat%RESET%
echo %DIM%  You do NOT need to run install.bat again.%RESET%
echo.
pause
