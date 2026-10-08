@echo off
chcp 65001 >nul
echo Avvio di Gastronomy Leads Agent...
if not exist "venv\Scripts\python.exe" (
    echo [ATTENZIONE] Ambiente virtuale non trovato. Avvio prima install.bat...
    call install.bat
)
start "" .\venv\Scripts\pythonw.exe main.py
exit
