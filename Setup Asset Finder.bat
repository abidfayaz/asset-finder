@echo off
rem One-time setup for the Asset Finder. Double-click this ONCE on a new computer.
rem After that, use "Start Asset Finder.bat" every day.

title Asset Finder - one-time setup
cd /d "%~dp0"

echo Looking for Python on this computer...

rem Try the Python launcher first (installed with Python from python.org),
rem then plain "python". Each is only accepted if it really runs Python 3 -
rem Windows has a placeholder "python" that does nothing when Python is missing.
set "PYTHON_CMD="
py -3 -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3"
if defined PYTHON_CMD goto found_python

python -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=python"
if defined PYTHON_CMD goto found_python

goto no_python

:found_python
%PYTHON_CMD% setup_asset_finder.py %*
echo.
echo Press any key to close this window.
pause >nul
exit /b

:no_python
echo.
echo ----------------------------------------------------------------
echo   Python is not installed on this computer
echo ----------------------------------------------------------------
echo.
echo The Asset Finder needs Python. It is free and takes about 5 minutes:
echo.
echo   1. Go to  https://www.python.org/downloads/
echo   2. Click the yellow "Download Python" button and open the file.
echo   3. On the first screen, TICK the box "Add python.exe to PATH".
echo   4. Click "Install Now" and wait until it says it is finished.
echo   5. Double-click "Setup Asset Finder.bat" again.
echo.
echo Press any key to close this window.
pause >nul
exit /b 1
