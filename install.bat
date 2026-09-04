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
    echo [ERROR] py launcher was not found.
    echo Please install Python 3.12 and enable the py launcher.
    echo.
    if "%MTPDFLOGO_NO_PAUSE%"=="1" exit /b 1
    pause
    exit /b 1
)

%PYTHON_CMD% --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python 3.12 was not found with py -3.12.
    echo Please install Python 3.12 before running this installer.
    echo.
    if "%MTPDFLOGO_NO_PAUSE%"=="1" exit /b 1
    pause
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo [1/3] Creating virtual environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 goto :install_failed
) else (
    echo [1/3] Existing virtual environment found.
)

echo [2/3] Updating pip...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto :install_failed

echo [3/3] Installing MTPDFLogo and dependencies...
"%PYTHON_EXE%" -m pip install "%PROJECT_DIR%."
if errorlevel 1 goto :install_failed

echo.
echo Installation finished.
echo Run start.bat to open MTPDFLogo.
echo.
if "%MTPDFLOGO_NO_PAUSE%"=="1" exit /b 0
pause
exit /b 0

:install_failed
echo.
echo [ERROR] Installation failed.
echo Please check your internet connection and Python 3.12 installation.
echo.
if "%MTPDFLOGO_NO_PAUSE%"=="1" exit /b 1
pause
exit /b 1
