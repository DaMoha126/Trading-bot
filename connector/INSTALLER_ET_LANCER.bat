@echo off
cd /d "%~dp0"
echo Ben Forex Lab - Connecteur MT5 DEMO uniquement
echo Ouvre MT5 sur un compte DEMO en USD avant de continuer.
echo Cette installation utilise Python, MetaTrader5 et Cloudflare Tunnel.
py -3 --version
if errorlevel 1 (
 echo Installer Python 3.10 ou plus avec le lanceur py puis relancer.
 pause
 exit /b 1
)
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install MetaTrader5
if errorlevel 1 goto :failure
where cloudflared >nul 2>nul
if errorlevel 1 (
 winget install --id Cloudflare.cloudflared --exact --accept-package-agreements --accept-source-agreements
)
.venv\Scripts\python.exe launch.py
pause
exit /b
:failure
echo Echec de l'installation. Verifier la connexion et Python 64 bits.
pause
