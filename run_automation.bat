@echo off
setlocal

set "PROJECT_ROOT=C:\Mail"
set "PYTHON_EXECUTABLE=C:\Mail\.venv\Scripts\python.exe"
set "AUTOMATION_RUNNER=C:\Mail\src\automation_runner.py"

cd /d "%PROJECT_ROOT%"

echo ========================================
echo CUSTOMER CASE AUTOMATION
echo ========================================
echo Starting automation...
echo Project: %PROJECT_ROOT%
echo Python: %PYTHON_EXECUTABLE%
echo.

"%PYTHON_EXECUTABLE%" "%AUTOMATION_RUNNER%"
set "RUN_EXIT_CODE=%ERRORLEVEL%"

echo.
echo Automation finished with exit code: %RUN_EXIT_CODE%
endlocal & exit /b %RUN_EXIT_CODE%
