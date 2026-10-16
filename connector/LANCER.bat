@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Lancer INSTALLER_ET_LANCER.bat une premiere fois.
 pause
 exit /b 1
)
.venv\Scripts\python.exe launch.py
pause
