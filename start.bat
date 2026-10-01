@echo off
cd /d "%~dp0"

set "PYCMD="
where python >nul 2>nul
if not errorlevel 1 set "PYCMD=python"
if defined PYCMD goto run

where py >nul 2>nul
if not errorlevel 1 set "PYCMD=py -3"
if defined PYCMD goto run

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYCMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if defined PYCMD goto run

echo [Error] Python 3.10+ is required but was not found.
echo Please install Python from https://www.python.org/downloads/
pause
exit /b 1

:run
echo Starting 86 Wubi Typing Trainer...
echo If the browser does not open, visit http://127.0.0.1:8765
%PYCMD% app.py
pause
