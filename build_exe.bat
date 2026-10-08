@echo off
chcp 65001 >nul
echo ========================================================
echo   Compilazione Eseguibile Gastronomy Leads Agent
echo ========================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ATTENZIONE] Ambiente virtuale non trovato. Avvio install.bat...
    call install.bat
)

:: Assicura che l'icona sia presente
if not exist "app_icon.ico" (
    echo Generazione icona...
    call .\venv\Scripts\python.exe create_icon.py
)

:: Trova il percorso locale dei browser di Playwright
set PLAYWRIGHT_DIR=%LOCALAPPDATA%\ms-playwright

echo Compilazione con PyInstaller...
set PLAYWRIGHT_BROWSERS_PATH=0

if exist "%PLAYWRIGHT_DIR%" (
    .\venv\Scripts\python.exe -m PyInstaller --noconfirm --onedir --windowed --icon "app_icon.ico" --add-data "app_icon.ico;." --add-data "%PLAYWRIGHT_DIR%;playwright\driver\package\.local-browsers" --name "GastronomyLeadsAgent" "main.py"
) else (
    .\venv\Scripts\python.exe -m PyInstaller --noconfirm --onedir --windowed --icon "app_icon.ico" --add-data "app_icon.ico;." --name "GastronomyLeadsAgent" "main.py"
)

echo.
echo ========================================================
echo   COMPILAZIONE TERMINATA!
echo   L'applicazione e' pronta nella cartella dist\GastronomyLeadsAgent
echo ========================================================
echo.
pause
