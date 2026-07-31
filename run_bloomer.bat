@echo off
setlocal
cd /d "%~dp0"

where py.exe >nul 2>nul
if not errorlevel 1 (
    py -3 bloomer.py
    goto finished
)

where python.exe >nul 2>nul
if not errorlevel 1 (
    python bloomer.py
    goto finished
)

where python3.exe >nul 2>nul
if not errorlevel 1 (
    python3 bloomer.py
    goto finished
)

echo Python 3 was not found.
echo Install it from https://www.python.org/downloads/windows/
echo During setup, enable "Add python.exe to PATH" or install the Python launcher.
pause
exit /b 1

:finished
set "bloomer_exit=%errorlevel%"
if not "%bloomer_exit%"=="0" pause
exit /b %bloomer_exit%
