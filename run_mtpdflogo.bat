@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\pythonw.exe"
set "PYTHONPATH=%PROJECT_DIR%app"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python environment was not found:
    echo         %PYTHON_EXE%
    echo.
    echo Please create or repair the project .venv first.
    pause
    exit /b 1
)

start "MTPDFLogo" "%PYTHON_EXE%" -m mtpdflogo
exit /b 0
