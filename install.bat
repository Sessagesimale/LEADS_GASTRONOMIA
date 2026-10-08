@echo off
chcp 65001 >nul
echo ========================================================
echo   Installazione Gastronomy Leads Agent su Nuovo PC
echo ========================================================
echo.

:: Verifica se Python e' installato
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERRORE] Python non e' installato o non e' presente nel PATH di sistema.
    echo Scarica e installa Python 3.10+ da https://www.python.org/
    echo Assicurati di selezionare la spunta "Add python.exe to PATH".
    pause
    exit /b 1
)

echo [1/4] Creazione ambiente virtuale (venv)...
if not exist "venv" (
    python -m venv venv
) else (
    echo       Ambiente virtuale gia' presente.
)

echo.
echo [2/4] Aggiornamento pip...
call .\venv\Scripts\python.exe -m pip install --upgrade pip

echo.
echo [3/4] Installazione librerie da requirements.txt...
call .\venv\Scripts\pip.exe install -r requirements.txt

echo.
echo [4/4] Installazione dei browser Playwright (Chromium)...
call .\venv\Scripts\playwright.exe install chromium

echo.
echo ========================================================
echo   INSTALLAZIONE COMPLETATA CON SUCCESSO!
echo ========================================================
echo - Per avviare l'app: esegui run.bat
echo - Per compilare l'eseguibile (.exe): esegui build_exe.bat
echo.
pause
