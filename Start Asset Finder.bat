@echo off
rem Double-click this file to open the Asset Finder in your browser.
rem It only starts the app. It does not install anything.

title Asset Finder - close this window to stop the app
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto not_installed

rem The first time only: offer a desktop shortcut. The answer is remembered.
if exist ".shortcut_offered" goto launch
echo.
choice /c YN /n /t 30 /d N /m "Put a shortcut to the Asset Finder on your desktop? Press Y for yes, N for no: "
if errorlevel 2 goto shortcut_done
powershell -NoProfile -Command "$desktop = [Environment]::GetFolderPath('Desktop'); $link = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Asset Finder.lnk')); $link.TargetPath = '%~dp0Start Asset Finder.bat'; $link.WorkingDirectory = '%~dp0'; $link.IconLocation = '%SystemRoot%\System32\shell32.dll,22'; $link.Save()"
if errorlevel 1 (
    echo Could not create the shortcut. You can still start the app from this folder.
) else (
    echo Shortcut created on your desktop: "Asset Finder".
)
:shortcut_done
type nul > ".shortcut_offered"

:launch
echo.
".venv\Scripts\python.exe" launcher.py
if errorlevel 1 (
    echo.
    echo Press any key to close this window.
    pause > nul
)
exit /b

:not_installed
echo.
echo The Asset Finder is not set up on this computer yet.
echo Double-click "Setup Asset Finder.bat" first - you only need to do it once.
echo Then double-click this file again.
echo.
pause
exit /b 1
