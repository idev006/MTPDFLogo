@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\pythonw.exe"
set "PYTHONPATH=%PROJECT_DIR%app"

if not exist "%PYTHON_EXE%" (
    echo ยังไม่ได้ติดตั้งโปรแกรม
    echo กรุณากด install.bat ก่อน
    echo.
    pause
    exit /b 1
)

start "MTPDFLogo" "%PYTHON_EXE%" -m mtpdflogo
exit /b 0
