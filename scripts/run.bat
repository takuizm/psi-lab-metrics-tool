@echo off
title PSI Lab Metrics Tool - Running...

echo ==========================================
echo   PSI Lab Metrics Tool - Execute
echo ==========================================
echo.

REM Check virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Setup not completed
    echo.
    echo Please run setup.bat first
    pause
    exit /b 1
)

REM Activate virtual environment
echo Preparing environment...
call venv\Scripts\activate.bat

REM Load environment variables
if exist ".env" (
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        set "%%a=%%b"
    )
)

REM Check API key
if "%PSI_API_KEY%"=="your_api_key_here" (
    echo [ERROR] PSI API key not configured
    echo.
    echo Please open .env file and set your API key
    echo PSI_API_KEY=your_api_key_here
    echo.
    pause
    exit /b 1
)

if "%PSI_API_KEY%"=="" (
    echo [ERROR] PSI API key not configured
    echo.
    echo Please open .env file and set your API key
    echo PSI_API_KEY=your_api_key_here
    echo.
    pause
    exit /b 1
)

REM Check configuration files
if not exist "config\config.yaml" (
    echo [ERROR] Configuration file not found
    echo.
    echo Please run setup.bat to complete setup
    pause
    exit /b 1
)

if not exist "input\targets.csv" (
    echo [ERROR] Target file not found
    echo.
    echo Please create input\targets.csv and set target URLs
    pause
    exit /b 1
)

echo [OK] Configuration check completed
echo.

REM Execution options
echo Select execution method:
echo.
echo [1] Mobile + Desktop (Recommended)
echo [2] Mobile only
echo [3] Desktop only
echo [4] Dry run (Configuration check only)
echo [5] Exit
echo.
set /p choice="Please select (1-5): "

if "%choice%"=="1" (
    set strategy=both
    set dryrun=
    echo.
    echo Running Mobile and Desktop measurement
) else if "%choice%"=="2" (
    set strategy=mobile
    set dryrun=
    echo.
    echo Running Mobile measurement only
) else if "%choice%"=="3" (
    set strategy=desktop
    set dryrun=
    echo.
    echo Running Desktop measurement only
) else if "%choice%"=="4" (
    set strategy=both
    set dryrun=--dry-run
    echo.
    echo Running dry run (configuration check)
) else if "%choice%"=="5" (
    echo.
    echo Exiting...
    pause
    exit /b 0
) else (
    echo.
    echo Invalid selection
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Starting Measurement
echo ==========================================
echo.

REM Execute Python
python -m src.cli.psi_main --strategy %strategy% %dryrun%

if %errorlevel% equ 0 (
    echo.
    echo ==========================================
    echo   Measurement Completed!
    echo ==========================================
    echo.
    echo Result files:
    echo   - JSON: output\json\
    echo   - CSV:  output\csv\psi_metrics.csv
    echo.
    echo Log file:
    echo   - logs\execution.log
    echo.
) else (
    echo.
    echo ==========================================
    echo   Error Occurred
    echo ==========================================
    echo.
    echo Please check log file for details:
    echo   - logs\execution.log
    echo.
)

echo Press any key to exit...
pause > nul
