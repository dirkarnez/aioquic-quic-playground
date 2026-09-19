@REM run as Administrator
@echo off

set DOWNLOADS_DIR=%USERPROFILE%\Downloads

@REM set PREFIX=D:\Softwares
set PREFIX=%DOWNLOADS_DIR%

set PYTHON_DIR=%PREFIX%\python-3.13.9-amd64-portable

set PATH=^
%PYTHON_DIR%;^
%PYTHON_DIR%\Scripts;^
%DOWNLOADS_DIR%\PortableGit\bin;^
%DOWNLOADS_DIR%\PortableGit\usr\bin;

python -c "import sys; print(f""Does this python have GIL: {hasattr(sys, '_is_gil_enabled') and sys._is_gil_enabled()}"")"
python -m main

pause
