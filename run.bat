@echo off
setlocal
set "PYTHON=C:\Users\Admin\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not exist "%PYTHON%" (
    echo Python was not found at:
    echo %PYTHON%
    echo Edit run.bat to set PYTHON to your Python executable.
    pause
    exit /b 1
)
cd /d "%~dp0"
"%PYTHON%" app.py
endlocal
