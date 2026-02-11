@echo off
REM ========================================
REM HomeGym - Code Quality & Formatting
REM ========================================

echo.
echo ========================================
echo   HomeGym Code Quality Tools
echo ========================================
echo.

REM Aktiviere Virtual Environment
call .venv\Scripts\activate.bat

echo [1/4] Formatiere Code mit Black...
black core/ config/ ai_coach/ --exclude migrations
if errorlevel 1 (
    echo FEHLER: Black konnte nicht ausgefuehrt werden!
    pause
    exit /b 1
)

echo.
echo [2/4] Sortiere Imports mit isort...
isort core/ config/ ai_coach/ --skip migrations
if errorlevel 1 (
    echo FEHLER: isort konnte nicht ausgefuehrt werden!
    pause
    exit /b 1
)

echo.
echo [3/4] Pruefe Code mit flake8...
flake8 core/ config/ --count --statistics
if errorlevel 1 (
    echo WARNUNG: flake8 hat Probleme gefunden!
    echo Bitte Warnings pruefen und beheben.
)

echo.
echo [4/4] Pruefe Type Hints mit mypy...
mypy core/ config/ --config-file pyproject.toml
if errorlevel 1 (
    echo WARNUNG: mypy hat Probleme gefunden!
    echo Type Hints sind optional, aber empfohlen.
)

echo.
echo ========================================
echo   Code Quality Check abgeschlossen!
echo ========================================
echo.
echo Naechste Schritte:
echo   1. git add .
echo   2. git commit -m "Your message"
echo   3. Pre-commit hooks laufen automatisch!
echo.

pause
