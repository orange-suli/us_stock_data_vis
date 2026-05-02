@echo off
chcp 65001 >nul
echo ============================================
echo   Building Market Chart Desktop EXE
echo ============================================
echo.

:: Check PyInstaller
conda run -n nasdaq pip install pyinstaller -q
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install PyInstaller
    pause
    exit /b 1
)

:: Clean previous build
rmdir /s /q build dist 2>nul
del /q *.spec 2>nul

:: Build
echo [INFO] Building EXE...
conda run -n nasdaq pyinstaller ^
    --onefile ^
    --windowed ^
    --name MarketChart ^
    --add-data "app/templates;app/templates" ^
    desktop_app.py

if %errorlevel% neq 0 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete: dist\MarketChart.exe
echo ============================================
pause
