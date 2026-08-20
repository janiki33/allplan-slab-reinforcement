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

rem Fassung, die das Sync-Skript mindestens haben muss. Verhindert, dass eine
rem veraltete Kopie aus einem Cache stillschweigend durchlaeuft.
set "NEEDVERSION=2"

set "CACHEDIR=%LOCALAPPDATA%\AllplanSlabReinforcementSync"
set "PS1=%~dp0Sync-SlabReinforcement.ps1"

echo ============================================================
echo  SlabReinforcement aktualisieren
echo  Quelle : %REPO% @ %BRANCH%
echo  Ziel   : %TARGET%
echo ============================================================
echo.

rem Liegt das Sync-Skript daneben, wird es benutzt. Sonst aus GitHub holen.
if exist "%PS1%" goto :check

set "PS1=%CACHEDIR%\Sync-SlabReinforcement.ps1"
if not exist "%CACHEDIR%" mkdir "%CACHEDIR%" >nul 2>&1

echo Hole Sync-Skript von GitHub ...

rem Bewusst ueber die API statt ueber raw.githubusercontent.com: der CDN dort
rem liefert nach einem Push noch minutenlang den alten Stand aus.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $u='https://api.github.com/repos/%REPO%/contents/tools/Sync-SlabReinforcement.ps1?ref='+[uri]::EscapeDataString('%TOOLBRANCH%'); $h=@{'Accept'='application/vnd.github.raw';'User-Agent'='AllplanSlabReinforcementSync';'Cache-Control'='no-cache'}; Invoke-WebRequest -Uri $u -Headers $h -UseBasicParsing -TimeoutSec 60 -OutFile '%CACHEDIR%\Sync-SlabReinforcement.ps1.new'; Move-Item -LiteralPath '%CACHEDIR%\Sync-SlabReinforcement.ps1.new' -Destination '%CACHEDIR%\Sync-SlabReinforcement.ps1' -Force"

if not errorlevel 1 goto :check

if exist "%PS1%" (
    echo.
    echo   Warnung: Download fehlgeschlagen - pruefe die gespeicherte Fassung.
    echo.
    goto :check
)

echo.
echo   FEHLER: Sync-Skript konnte nicht geladen werden und es liegt keine
echo           gespeicherte Fassung vor. Internetverbindung pruefen.
echo.
pause
exit /b 3

:check
rem Fassung pruefen, damit kein alter Zwischenstand unbemerkt durchlaeuft.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$m = Select-String -LiteralPath '%PS1%' -Pattern 'ScriptVersion\s*=\s*(\d+)' | Select-Object -First 1; if (-not $m) { exit 1 }; if ([int]$m.Matches[0].Groups[1].Value -lt %NEEDVERSION%) { exit 1 }; exit 0"

if not errorlevel 1 goto :run

echo.
echo   FEHLER: Das geladene Sync-Skript ist aelter als Fassung %NEEDVERSION%.
echo           Vermutlich hat ein Cache eine veraltete Kopie geliefert.
echo           Der Zwischenspeicher wird jetzt geloescht - bitte diese Datei
echo           einfach noch einmal starten.
echo.
del "%CACHEDIR%\Sync-SlabReinforcement.ps1" >nul 2>&1
pause
exit /b 4

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
