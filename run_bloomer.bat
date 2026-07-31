@echo off
setlocal
cd /d "%~dp0"

where py.exe >nul 2>nul
if not errorlevel 1 (
    set "bloomer_python=py -3"
    goto dependencies
)

where python.exe >nul 2>nul
if not errorlevel 1 (
    set "bloomer_python=python"
    goto dependencies
)

where python3.exe >nul 2>nul
if not errorlevel 1 (
    set "bloomer_python=python3"
    goto dependencies
)

echo Python 3 was not found.
echo Install it from https://www.python.org/downloads/windows/
echo During setup, enable "Add python.exe to PATH" or install the Python launcher.
pause
exit /b 1

:dependencies
%bloomer_python% -c "from winrt.windows.graphics.imaging import SoftwareBitmap; from winrt.windows.media.ocr import OcrEngine" >nul 2>nul
if errorlevel 1 (
    echo Installing Bloomer's local Windows OCR components...
    %bloomer_python% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Could not install the OCR components.
        echo Run: %bloomer_python% -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

%bloomer_python% bloomer.py

:finished
set "bloomer_exit=%errorlevel%"
if not "%bloomer_exit%"=="0" pause
exit /b %bloomer_exit%
