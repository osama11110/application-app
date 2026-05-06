@echo off
echo ============================================
echo  Job Application Automation - Setup
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

echo [1/3] Installing Python packages...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Playwright browser (Chromium)...
playwright install chromium
if errorlevel 1 (
    echo ERROR: Playwright install failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Setup complete!
echo.
echo ============================================
echo  NEXT STEPS:
echo ============================================
echo  1. Place your CV in:   cv\cv.pdf
echo     (PDF or DOCX accepted, rename to cv.pdf)
echo.
echo  2. Edit config.yaml:
echo     - Add your Anthropic API key
echo     - Add your login credentials per site
echo     - Adjust filters (salary, job type, etc.)
echo.
echo  3. Run the tool:
echo     python main.py
echo.
echo  Optional flags:
echo     python main.py --dry-run    (search only, no apply)
echo     python main.py --site linkedin  (one site only)
echo ============================================
echo.
pause
