@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\python.exe"
set "DIST_DIR=%PROJECT_DIR%dist"
set "STAGE_DIR=%PROJECT_DIR%build\installer\MTPDFLogo"
set "ZIP_PATH=%DIST_DIR%\MTPDFLogo-installer.zip"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python environment was not found:
    echo         %PYTHON_EXE%
    echo.
    echo Run install.bat first.
    pause
    exit /b 1
)

echo [1/4] Ensuring build/test dependencies...
"%PYTHON_EXE%" -m pip install -e "%PROJECT_DIR%.[dev]"
if errorlevel 1 goto build_failed

echo [2/4] Running tests and lint...
"%PYTHON_EXE%" -m ruff check app tests
if errorlevel 1 goto build_failed
"%PYTHON_EXE%" -m pytest -q
if errorlevel 1 goto build_failed

echo [3/4] Preparing installer files...
if exist "%STAGE_DIR%" rmdir /s /q "%STAGE_DIR%"
mkdir "%STAGE_DIR%"
if errorlevel 1 goto build_failed

robocopy "%PROJECT_DIR%app" "%STAGE_DIR%\app" /E /XD __pycache__ /XF *.pyc >nul
if errorlevel 8 goto build_failed
robocopy "%PROJECT_DIR%config" "%STAGE_DIR%\config" /E >nul
if errorlevel 8 goto build_failed
robocopy "%PROJECT_DIR%docs" "%STAGE_DIR%\docs" /E >nul
if errorlevel 8 goto build_failed
robocopy "%PROJECT_DIR%tests" "%STAGE_DIR%\tests" /E /XD __pycache__ .pytest_cache /XF *.pyc >nul
if errorlevel 8 goto build_failed

copy "%PROJECT_DIR%pyproject.toml" "%STAGE_DIR%\pyproject.toml" >nul
copy "%PROJECT_DIR%install.bat" "%STAGE_DIR%\install.bat" >nul
copy "%PROJECT_DIR%start.bat" "%STAGE_DIR%\start.bat" >nul
copy "%PROJECT_DIR%start-debug.bat" "%STAGE_DIR%\start-debug.bat" >nul
copy "%PROJECT_DIR%run_mtpdflogo.bat" "%STAGE_DIR%\run_mtpdflogo.bat" >nul
copy "%PROJECT_DIR%README_DISTRIBUTION_TH.md" "%STAGE_DIR%\README_DISTRIBUTION_TH.md" >nul

echo [4/4] Creating installer zip...
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
if exist "%ZIP_PATH%" del "%ZIP_PATH%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -LiteralPath '%STAGE_DIR%' -DestinationPath '%ZIP_PATH%' -Force"
if errorlevel 1 goto build_failed

echo.
echo Installer package finished:
echo %ZIP_PATH%
echo.
exit /b 0

:build_failed
echo.
echo [ERROR] Build failed.
echo.
pause
exit /b 1
