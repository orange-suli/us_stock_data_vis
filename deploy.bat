@echo off
chcp 65001 >nul
title Market Chart

echo ============================================
echo   Market Chart — One-Click Deploy
echo ============================================
echo.

:: Check conda
where conda >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] conda not found. Please install Miniconda first:
    echo   https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)
echo [OK] conda found

:: Create conda env if not exists
call conda info --envs 2>nul | findstr /c:"nasdaq " >nul
if %errorlevel% neq 0 (
    echo [INFO] Creating conda environment 'nasdaq'...
    call conda create -n nasdaq python=3.12 -y
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create conda environment
        pause
        exit /b 1
    )
    echo [OK] Environment 'nasdaq' created
) else (
    echo [OK] Environment 'nasdaq' already exists
)

:: Install / update dependencies
echo [INFO] Installing dependencies...
call conda run -n nasdaq pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed

:: Launch browser after a short delay
echo [INFO] Starting server at http://localhost:5000
start "" http://localhost:5000

:: Start Flask
echo.
echo ============================================
echo   Server running. Press Ctrl+C to stop.
echo ============================================
call conda run -n nasdaq python app/app.py

pause
