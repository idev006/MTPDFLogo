@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON_CMD=py -3.12"
set "VENV_DIR=%PROJECT_DIR%.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

echo.
echo ==========================================
echo  MTPDFLogo Installer
echo ==========================================
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo [ERROR] ไม่พบ py launcher
    echo กรุณาติดตั้ง Python 3.12 และเลือก Add python.exe to PATH
    echo.
    pause
    exit /b 1
)

%PYTHON_CMD% --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] ไม่พบ Python 3.12 ผ่านคำสั่ง py -3.12
    echo กรุณาติดตั้ง Python 3.12 ก่อนใช้งาน
    echo.
    pause
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo [1/3] กำลังสร้าง virtual environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 goto install_failed
) else (
    echo [1/3] พบ virtual environment เดิมแล้ว
)

echo [2/3] กำลังอัปเดต pip...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto install_failed

echo [3/3] กำลังติดตั้ง MTPDFLogo และ dependencies...
"%PYTHON_EXE%" -m pip install -e "%PROJECT_DIR%."
if errorlevel 1 goto install_failed

echo.
echo ติดตั้งเสร็จแล้ว
echo กด start.bat เพื่อเปิดโปรแกรม
echo.
pause
exit /b 0

:install_failed
echo.
echo [ERROR] ติดตั้งไม่สำเร็จ
echo กรุณาตรวจสอบ internet connection และ Python 3.12
echo.
pause
exit /b 1
