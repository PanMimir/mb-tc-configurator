@echo off
REM ============================================================
REM build_exe.bat - skrypt budujacy plik wykonywalny .exe na Windowsie
REM
REM Uruchamia kolejno:
REM   1. Tworzenie virtualenv (jesli nie istnieje)
REM   2. Aktywacja virtualenv
REM   3. Instalacja zaleznosci runtime + pyinstaller
REM   4. Budowa .exe wedlug pliku mb_tc_configurator.spec
REM   5. Wyswietlenie sciezki do gotowego pliku
REM
REM Wymagania: zainstalowany Python 3.11+ widoczny w PATH jako "python".
REM ============================================================

setlocal enableextensions

echo.
echo ============================================================
echo  MB-TC Configurator - budowa pliku .exe
echo ============================================================
echo.

REM Przejscie do katalogu skryptu (na wypadek odpalenia z innego miejsca)
cd /d "%~dp0"

REM 1) Sprawdzenie wersji Pythona
where python >nul 2>nul
if errorlevel 1 (
    echo [BLAD] Python nie jest dostepny w PATH.
    echo Zainstaluj Python 3.11+ ze strony https://www.python.org/downloads/
    echo i podczas instalacji zaznacz "Add Python to PATH".
    pause
    exit /b 1
)
python --version

REM 2) Tworzenie venv jesli brak
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo [INFO] Tworze srodowisko virtualenv w .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [BLAD] Nie udalo sie utworzyc virtualenv.
        pause
        exit /b 1
    )
)

REM 3) Aktywacja venv
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [BLAD] Nie udalo sie aktywowac virtualenv.
    pause
    exit /b 1
)

REM 4) Instalacja zaleznosci
echo.
echo [INFO] Instaluje zaleznosci runtime ...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [BLAD] Instalacja zaleznosci runtime nie powiodla sie.
    pause
    exit /b 1
)

echo.
echo [INFO] Instaluje PyInstaller ...
pip install -r requirements-build.txt
if errorlevel 1 (
    echo [BLAD] Instalacja PyInstallera nie powiodla sie.
    pause
    exit /b 1
)

REM 5) Czyszczenie poprzednich buildow
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM 6) Budowa .exe
echo.
echo [INFO] Buduje plik wykonywalny ...
pyinstaller --clean mb_tc_configurator.spec
if errorlevel 1 (
    echo [BLAD] Budowa .exe nie powiodla sie.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  GOTOWE!
echo ============================================================
if exist "dist\MB-TC-Configurator.exe" (
    echo Plik wykonywalny:  %CD%\dist\MB-TC-Configurator.exe
    echo Mozesz go skopiowac w dowolne miejsce i uruchomic dwuklikiem.
) else (
    echo [UWAGA] Nie znaleziono pliku dist\MB-TC-Configurator.exe.
    echo Sprawdz log powyzej.
)
echo.
pause
endlocal
