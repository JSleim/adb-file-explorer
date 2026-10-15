@echo off
setlocal

echo [1/6] Cleaning up previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "cpp\build" rmdir /s /q "cpp\build"
if exist "ADB Explorer.spec" del "ADB Explorer.spec"

:: Create a clean Python environment
python -m venv venv
call venv\Scripts\activate.bat

echo [2/6] Installing required packages...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo [3/6] Building native Windows drag source...
where cl >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    cmake -S cpp -B cpp\build -A x64
) else (
    where g++ >nul 2>nul
    if errorlevel 1 (
        echo Install Visual Studio C++ Build Tools or MinGW-w64.
        exit /b 1
    )
    cmake -S cpp -B cpp\build -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release
)
if %ERRORLEVEL% NEQ 0 (
    echo Native build configuration failed. Check that CMake and a C++ compiler are installed.
    exit /b %ERRORLEVEL%
)
cmake --build cpp\build --config Release
if %ERRORLEVEL% NEQ 0 (
    echo Native Windows drag source build failed.
    exit /b %ERRORLEVEL%
)

echo [4/6] Building ADB Explorer...
pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --icon "assets\adb-explorer.ico" ^
    --name "ADB Explorer" ^
    --add-data "logging_config.py;." ^
    --add-data "assets\adb-explorer.ico;assets" ^
    --add-binary "cpp\build\Release\adb_drag_source.dll;." ^
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

echo [5/6] Cleaning up...
rmdir /s /q "__pycache__" 2>nul
rmdir /s /q "venv" 2>nul

if exist "dist\ADB Explorer.exe" (
    echo [6/6] Build successful! Launching application...
    start "" /B "dist\ADB Explorer.exe"
) else (
    echo [ERROR] Executable not found in dist folder!
    pause
    exit /b 1
)

echo.
echo Done! The application should now be running.
pause
