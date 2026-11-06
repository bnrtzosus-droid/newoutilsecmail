@echo off
echo ============================================
echo   INSTALLATION - Detecteur de Comptes
echo ============================================
echo.

echo [1/3] Verification de Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Python non installe.
    echo Telechargez Python sur https://www.python.org/downloads/
    echo Cochez "Add Python to PATH" pendant l'installation.
    pause
    exit /b 1
)
echo OK - Python detecte.

echo.
echo [2/3] Installation des dependances...
pip install playwright
if errorlevel 1 (
    echo ERREUR lors de l'installation.
    pause
    exit /b 1
)

echo.
echo [3/3] Installation du navigateur Chromium...
playwright install chromium
if errorlevel 1 (
    echo ERREUR lors de l'installation de Chromium.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   INSTALLATION TERMINEE !
echo ============================================
echo.
echo Pour lancer le logiciel, double-cliquez sur:
echo   lancer_windows.bat
echo.
pause
