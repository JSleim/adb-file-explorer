@echo off
setlocal

echo [1/5] Cleaning up previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "ADB Explorer.spec" del "ADB Explorer.spec"

:: Create a clean Python environment
python -m venv venv
call venv\Scripts\activate.bat

echo [2/5] Installing required packages...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo [3/5] Building ADB Explorer...
pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "ADB Explorer" ^
    --add-data "logging_config.py;." ^
    --hidden-import="PyQt6.QtWidgets" ^
    --hidden-import="PyQt6.QtCore" ^
    --hidden-import="PyQt6.QtGui" ^
    --hidden-import="logging.handlers" ^
    --clean ^
    --noconsole ^
    --log-level=ERROR ^
    main.py

if %ERRORLEVEL% NEQ 0 (
    echo Build failed with error %ERRORLEVEL%
    pause
    exit /b %ERRORLEVEL%
)

echo [4/5] Cleaning up...
rmdir /s /q "__pycache__" 2>nul
rmdir /s /q "venv" 2>nul

if exist "dist\ADB Explorer.exe" (
    echo [5/5] Build successful! Launching application...
    start "" /B "dist\ADB Explorer.exe"
) else (
    echo [ERROR] Executable not found in dist folder!
    pause
    exit /b 1
)

echo.
echo Done! The application should now be running.
pause
