@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\python.exe"
set "PYTHONPATH=%PROJECT_DIR%app"

if not exist "%PYTHON_EXE%" (
    echo MTPDFLogo is not installed yet.
    echo Please run install.bat first.
    echo.
    pause
    exit /b 1
)

echo Starting MTPDFLogo in debug mode...
echo If the application fails to open, the error details will remain in this window.
echo.
"%PYTHON_EXE%" -m mtpdflogo
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo MTPDFLogo exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
