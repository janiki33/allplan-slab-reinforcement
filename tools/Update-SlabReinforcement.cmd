@echo off
rem ---------------------------------------------------------------------------
rem  SlabReinforcement aktualisieren
rem
rem  Doppelklick genuegt. Holt die aktuellen Dateien aus GitHub und schreibt sie
rem  in das Allplan-Benutzerverzeichnis.
rem
rem  Anderes Zielverzeichnis oder anderer Branch: die Zeilen TARGET bzw. BRANCH
rem  weiter unten anpassen.
rem
rem  Zusaetzliche Schalter werden an Sync-SlabReinforcement.ps1 durchgereicht,
rem  z. B. "Update-SlabReinforcement.cmd -Install" fuer den automatischen
rem  Abgleich alle 10 Minuten oder "-Uninstall" zum Abschalten. Nicht erneut
rem  -AllplanUsr / -Branch / -Repo uebergeben, die setzt diese Datei bereits.
rem ---------------------------------------------------------------------------

setlocal
title SlabReinforcement aktualisieren

set "REPO=janiki33/allplan-slab-reinforcement"
set "BRANCH=claude/new-session-8uzquy"
set "TOOLBRANCH=claude/slab-reinforcement-sync-nykay9"
set "TARGET=J:\Allplan\Usr\Janosch"

set "CACHEDIR=%LOCALAPPDATA%\AllplanSlabReinforcementSync"
set "PS1=%~dp0Sync-SlabReinforcement.ps1"

echo ============================================================
echo  SlabReinforcement aktualisieren
echo  Quelle : %REPO% @ %BRANCH%
echo  Ziel   : %TARGET%
echo ============================================================
echo.

rem Liegt das Sync-Skript daneben, wird es benutzt. Sonst aus GitHub holen.
if exist "%PS1%" goto :run

set "PS1=%CACHEDIR%\Sync-SlabReinforcement.ps1"
if not exist "%CACHEDIR%" mkdir "%CACHEDIR%" >nul 2>&1

echo Hole Sync-Skript von GitHub ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 -Headers @{'Cache-Control'='no-cache'} -Uri 'https://raw.githubusercontent.com/%REPO%/%TOOLBRANCH%/tools/Sync-SlabReinforcement.ps1' -OutFile '%CACHEDIR%\Sync-SlabReinforcement.ps1.new'; Move-Item -LiteralPath '%CACHEDIR%\Sync-SlabReinforcement.ps1.new' -Destination '%CACHEDIR%\Sync-SlabReinforcement.ps1' -Force"

if not errorlevel 1 goto :run

if exist "%PS1%" (
    echo.
    echo   Warnung: Download fehlgeschlagen - benutze die zuletzt gespeicherte Fassung.
    echo.
    goto :run
)

echo.
echo   FEHLER: Sync-Skript konnte nicht geladen werden und es liegt keine
echo           gespeicherte Fassung vor. Internetverbindung pruefen.
echo.
pause
exit /b 3

:run
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -AllplanUsr "%TARGET%" -Branch "%BRANCH%" -Repo "%REPO%" %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
    echo Fertig - alle Dateien sind auf dem Stand von GitHub.
) else if "%RC%"=="2" (
    echo FEHLER: %TARGET% ist nicht erreichbar. Netzlaufwerk verbunden?
) else (
    echo FEHLER: Mindestens eine Datei konnte nicht abgeglichen werden - siehe Meldungen oben.
)

echo.
echo Hinweis: Wurde eine .py-Datei aktualisiert, muss Allplan neu gestartet
echo          werden, damit die Aenderung wirkt.
echo.
pause
exit /b %RC%
