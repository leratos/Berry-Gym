@echo off
REM HomeGym Test Suite Runner (Windows)
REM Installiert Dependencies und führt Tests aus

echo.
echo ========================================
echo   HomeGym Test Suite Setup
echo ========================================
echo.

REM Check if venv exists
if not exist ".venv\" (
    echo [ERROR] Virtual Environment nicht gefunden!
    echo Bitte erst erstellen: python -m venv .venv
    exit /b 1
)

REM Activate venv
echo [1/3] Aktiviere Virtual Environment...
call .venv\Scripts\activate.bat

REM Install test dependencies
echo.
echo [2/3] Installiere Test-Dependencies...
pip install -q pytest pytest-django pytest-cov factory-boy faker

REM Run tests
echo.
echo [3/3] Führe Tests aus...
echo.
pytest -v --tb=short

echo.
echo ========================================
echo   Test-Lauf abgeschlossen!
echo ========================================
echo.
echo Für Coverage-Report: pytest --cov --cov-report=html
echo Dann öffne: htmlcov\index.html
echo.

pause
