@REM run as Administrator
@echo off

set DOWNLOADS_DIR=%USERPROFILE%\Downloads

@REM set PREFIX=D:\Softwares
set PREFIX=%DOWNLOADS_DIR%


set PYTHON_DIR=%PREFIX%\python-3.13.9-amd64-portable
set PATH=%PYTHON_DIR%;%PYTHON_DIR%\Scripts

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
pause
