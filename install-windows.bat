@echo off
REM Unity Logcat Viewer - Windows Installer
REM Installs Python 3, ADB, and dependencies automatically

title Unity Logcat Viewer - Installer
color 0A

echo.
echo ===============================================================
echo          Unity Logcat Viewer - Windows Installer
echo ===============================================================
echo.

REM Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] This installer needs administrator privileges for some operations.
    echo [!] Right-click and select "Run as administrator" if installation fails.
    echo.
)

REM Check for winget (Windows Package Manager)
where winget >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Windows Package Manager (winget) not found.
    echo [!] Please install it from the Microsoft Store (App Installer)
    echo [!] or download from: https://github.com/microsoft/winget-cli/releases
    echo.
    pause
    exit /b 1
)

echo Checking dependencies...
echo.

REM Check for Python
where python >nul 2>&1
if %errorLevel% neq 0 (
    echo [*] Python not found. Installing Python 3...
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements

    REM Refresh PATH
    call refreshenv >nul 2>&1

    REM Add Python to current session PATH
    for /f "tokens=*" %%i in ('where python 2^>nul') do set "PYTHON_PATH=%%~dpi"
    if defined PYTHON_PATH (
        set "PATH=%PYTHON_PATH%;%PATH%"
    )
) else (
    echo [OK] Python is installed
)

REM Check for ADB
where adb >nul 2>&1
if %errorLevel% neq 0 (
    echo [*] ADB not found. Installing Android Platform Tools...

    REM Create tools directory
    if not exist "%USERPROFILE%\platform-tools" (
        mkdir "%USERPROFILE%\platform-tools"
    )

    REM Download platform-tools
    echo [*] Downloading Android Platform Tools...
    powershell -Command "Invoke-WebRequest -Uri 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile '%TEMP%\platform-tools.zip'"

    echo [*] Extracting...
    powershell -Command "Expand-Archive -Path '%TEMP%\platform-tools.zip' -DestinationPath '%USERPROFILE%' -Force"

    REM Add to PATH permanently
    setx PATH "%PATH%;%USERPROFILE%\platform-tools" >nul 2>&1
    set "PATH=%PATH%;%USERPROFILE%\platform-tools"

    del "%TEMP%\platform-tools.zip" >nul 2>&1

    echo [OK] ADB installed to %USERPROFILE%\platform-tools
) else (
    echo [OK] ADB is installed
)

REM Install Python dependencies
echo.
echo [*] Installing Python dependencies...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet aiohttp

echo.
echo [OK] All dependencies installed!
echo.

REM Create run.bat launcher
echo @echo off > "%~dp0run.bat"
echo cd /d "%%~dp0" >> "%~dp0run.bat"
echo python logcat-web.py >> "%~dp0run.bat"
echo pause >> "%~dp0run.bat"

REM Create VBS launcher for double-click without console window
echo Set WshShell = CreateObject("WScript.Shell") > "%~dp0Unity Logcat Viewer.vbs"
echo WshShell.CurrentDirectory = "%~dp0" >> "%~dp0Unity Logcat Viewer.vbs"
echo WshShell.Run "python logcat-web.py", 1, False >> "%~dp0Unity Logcat Viewer.vbs"

echo ===============================================================
echo                   Installation Complete!
echo ===============================================================
echo.
echo   To run the viewer:
echo.
echo   Option 1: Double-click 'Unity Logcat Viewer.vbs'
echo.
echo   Option 2: Double-click 'run.bat'
echo.
echo   Option 3: Run in Command Prompt:
echo             python logcat-web.py
echo.
echo ===============================================================
echo.

set /p RUNNOW="Do you want to run the viewer now? (Y/N): "
if /i "%RUNNOW%"=="Y" (
    python "%~dp0logcat-web.py"
)

pause
