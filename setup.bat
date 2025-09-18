@echo off
echo ==========================================
echo   PSI Lab Metrics Tool - Setup (Windows)
echo ==========================================
echo.

REM Python check
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found
    echo.
    echo Please install Python 3.8 or later:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [OK] Python found
python --version

REM Create virtual environment
echo.
echo Creating virtual environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)

REM Activate virtual environment
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies - split into multiple lines to avoid long command issues
echo.
echo Installing required libraries...
pip install requests>=2.28.0
pip install PyYAML>=6.0
pip install pandas>=1.5.0
pip install click>=8.1.0
pip install python-dotenv>=0.19.0

if %errorlevel% neq 0 (
    echo [ERROR] Failed to install libraries
    pause
    exit /b 1
)

REM Create directories
echo.
echo Creating directories...
if not exist "config" mkdir config
if not exist "output" mkdir output
if not exist "output\json" mkdir output\json
if not exist "output\csv" mkdir output\csv
if not exist "logs" mkdir logs
if not exist "src" mkdir src

REM Copy configuration files
echo.
echo Preparing configuration files...
if not exist "config\config.yaml" (
    copy "config.example.yaml" "config\config.yaml" >nul
    echo [OK] config.yaml created
)

if not exist "config\targets.csv" (
    copy "targets.csv" "config\targets.csv" >nul
    echo [OK] targets.csv created
)

REM Create environment file
echo.
echo Creating environment file...
if not exist ".env" (
    echo PSI_API_KEY=your_api_key_here> .env
    echo [OK] .env file created
)

echo.
echo ==========================================
echo   Setup Complete!
echo ==========================================
echo.
echo Next Steps:
echo.
echo 1. Get PSI API key from Google Cloud Console
echo    https://console.cloud.google.com/
echo.
echo 2. Open .env file and set your API key
echo    PSI_API_KEY=your_api_key_here
echo.
echo 3. Open targets.csv and set target URLs
echo.
echo 4. Double-click run.bat to execute
echo.
echo ==========================================
pause
