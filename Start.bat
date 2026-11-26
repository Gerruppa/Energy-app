@echo off
rem Start PV app: dwuklik. Przy pierwszym starcie instaluje uv i zaleznosci.
chcp 65001 >nul
cd /d "%~dp0"

set "UV=uv"
where uv >nul 2>nul
if errorlevel 1 (
    if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe" (
        set "UV=%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe"
    ) else if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set "UV=%USERPROFILE%\.local\bin\uv.exe"
    ) else (
        echo Instaluje uv - menedzer Pythona, jednorazowo...
        winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
        if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe" (
            set "UV=%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe"
        ) else (
            echo Nie udalo sie zainstalowac uv. Zainstaluj go recznie: https://docs.astral.sh/uv/
            pause
            exit /b 1
        )
    )
)

rem Srodowisko skopiowane z innego folderu wskazuje na tamten kod: odtworz je.
set "PTH=.venv\Lib\site-packages\_editable_impl_pv_app.pth"
if exist "%PTH%" (
    findstr /L /I /C:"%~dp0src" "%PTH%" >nul || (
        echo Folder aplikacji zostal przeniesiony - odtwarzam srodowisko...
        rmdir /s /q .venv
    )
)

echo Uruchamiam PV app. Zamknij to okno, aby zatrzymac aplikacje.
"%UV%" run --frozen --no-dev python -m pv_app
if errorlevel 1 pause
