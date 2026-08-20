<#
.SYNOPSIS
    Synchronisiert die SlabReinforcement-Dateien aus GitHub in das lokale
    Allplan-Benutzerverzeichnis.

.DESCRIPTION
    Laedt die Skript- und Bibliotheksdateien direkt von raw.githubusercontent.com
    und schreibt sie nur dann, wenn sich der Inhalt tatsaechlich geaendert hat.
    GitHub ist dabei immer die Quelle der Wahrheit - lokale Aenderungen an den
    synchronisierten Dateien werden ueberschrieben.

    Bei einer Aenderung wird zusaetzlich der __pycache__-Ordner im Zielverzeichnis
    geleert, damit Allplan die neuen Module beim naechsten Start wirklich laedt.

.PARAMETER AllplanUsr
    Wurzel des Allplan-Benutzerverzeichnisses. Darunter werden
    PythonPartsScripts\SlabReinforcement und Library\SlabReinforcement erwartet.

.PARAMETER Branch
    Zu synchronisierender Git-Branch.

.PARAMETER IntervalSeconds
    Wenn gesetzt, laeuft das Skript dauerhaft und prueft im angegebenen Abstand
    erneut. Ohne diesen Parameter laeuft es genau einmal durch.

.PARAMETER RemoveStale
    Entfernt veraltete Dateien aus dem Zielordner (SlabReinforcement.py und
    SlabReinforcementScript.py aus frueheren Versionen). Das PythonPart ist
    inzwischen ein Python-Paket: der Ordner SlabReinforcement enthaelt ein
    __init__.py, die .pyp verweist auf SlabReinforcement.py - eine Datei, die
    es bewusst nicht gibt. Eine uebriggebliebene gleichnamige Datei wuerde den
    Paketordner verdecken.

.PARAMETER Install
    Registriert eine geplante Aufgabe (Task Scheduler), die diesen Sync bei der
    Anmeldung und danach alle 10 Minuten ausfuehrt.

.PARAMETER Uninstall
    Entfernt die mit -Install angelegte geplante Aufgabe wieder.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Sync-SlabReinforcement.ps1 -RemoveStale

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Sync-SlabReinforcement.ps1 -Install
#>

[CmdletBinding()]
param(
    [string]   $AllplanUsr     = 'J:\Allplan\Usr\Janosch',
    [string]   $Branch         = 'main',
    [string]   $Repo           = 'janiki33/allplan-slab-reinforcement',
    [int]      $IntervalSeconds = 0,
    [switch]   $RemoveStale,
    [switch]   $Install,
    [switch]   $Uninstall,
    [string]   $LogFile,
    [switch]   $Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# PowerShell 5.1 verhandelt sonst teilweise noch TLS 1.0 - GitHub lehnt das ab.
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$TaskName = 'AllplanSlabReinforcementSync'

# Quelle (Pfad im Repo) -> Ziel (Pfad relativ zu $AllplanUsr)
$FileMap = @(
    @{ Source = 'PythonPartsScripts/SlabReinforcement/__init__.py'
       Target = 'PythonPartsScripts\SlabReinforcement\__init__.py' }
    @{ Source = 'PythonPartsScripts/SlabReinforcement/slab_reinforcement.py'
       Target = 'PythonPartsScripts\SlabReinforcement\slab_reinforcement.py' }
    @{ Source = 'PythonPartsScripts/SlabReinforcement/contour_placement.py'
       Target = 'PythonPartsScripts\SlabReinforcement\contour_placement.py' }
    @{ Source = 'PythonPartsScripts/SlabReinforcement/opening_clipping.py'
       Target = 'PythonPartsScripts\SlabReinforcement\opening_clipping.py' }
    @{ Source = 'PythonPartsScripts/SlabReinforcement/opening_reinforcement.py'
       Target = 'PythonPartsScripts\SlabReinforcement\opening_reinforcement.py' }
    @{ Source = 'PythonPartsScripts/SlabReinforcement/lap_splitting.py'
       Target = 'PythonPartsScripts\SlabReinforcement\lap_splitting.py' }
    @{ Source = 'Library/SlabReinforcement/SlabReinforcement.pyp'
       Target = 'Library\SlabReinforcement\SlabReinforcement.pyp' }
)

# Dateien, die aus frueheren Versionen stammen und nicht mehr vorhanden sein duerfen.
$StaleFiles = @(
    'PythonPartsScripts\SlabReinforcement\SlabReinforcement.py'
    'PythonPartsScripts\SlabReinforcement\SlabReinforcementScript.py'
)


function Write-Log {
    param(
        [Parameter(Mandatory)][string] $Message,
        [ValidateSet('INFO', 'CHANGE', 'WARN', 'ERROR')][string] $Level = 'INFO'
    )

    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message

    if (-not $Quiet) {
        switch ($Level) {
            'CHANGE' { Write-Host $line -ForegroundColor Green }
            'WARN'   { Write-Host $line -ForegroundColor Yellow }
            'ERROR'  { Write-Host $line -ForegroundColor Red }
            default  { Write-Host $line }
        }
    }

    if ($LogFile) {
        try {
            $logDir = Split-Path -Parent $LogFile
            if ($logDir -and -not (Test-Path -LiteralPath $logDir)) {
                New-Item -ItemType Directory -Path $logDir -Force | Out-Null
            }
            Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
        }
        catch {
            # Ein nicht schreibbares Logfile darf den Sync nicht abbrechen.
        }
    }
}


function Get-Sha256 {
    param([Parameter(Mandatory)][byte[]] $Bytes)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-', '')
    }
    finally {
        $sha.Dispose()
    }
}


function Get-RemoteBytes {
    param([Parameter(Mandatory)][string] $Url)

    # Ueber -OutFile, damit der Inhalt nie durch eine String-Dekodierung laeuft -
    # sonst koennten Umlaute und Zeilenenden je nach PowerShell-Version kippen.
    # 'no-cache' umgeht den CDN-Cache von raw.githubusercontent.com, der sonst
    # bis zu fuenf Minuten alte Staende ausliefert.
    $temp = [System.IO.Path]::GetTempFileName()
    try {
        Invoke-WebRequest -Uri $Url `
                          -Headers @{ 'Cache-Control' = 'no-cache'; 'Pragma' = 'no-cache' } `
                          -UseBasicParsing -TimeoutSec 60 -OutFile $temp | Out-Null

        $bytes = [System.IO.File]::ReadAllBytes($temp)
        if ($bytes.Length -eq 0) {
            throw "Leere Antwort von $Url"
        }
        return $bytes
    }
    finally {
        Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
    }
}


function Clear-PyCache {
    param([Parameter(Mandatory)][string] $Directory)

    $cache = Join-Path $Directory '__pycache__'
    if (Test-Path -LiteralPath $cache) {
        try {
            Remove-Item -LiteralPath $cache -Recurse -Force
            Write-Log "__pycache__ geleert: $cache"
        }
        catch {
            Write-Log "__pycache__ konnte nicht geleert werden ($cache): $($_.Exception.Message)" -Level WARN
        }
    }
}


function Invoke-SyncPass {
    $baseUrl = "https://raw.githubusercontent.com/$Repo/$Branch"
    $changed = 0
    $failed  = 0
    $touchedDirs = New-Object System.Collections.Generic.HashSet[string]

    foreach ($entry in $FileMap) {
        $url        = "$baseUrl/$($entry.Source)"
        $targetPath = Join-Path $AllplanUsr $entry.Target
        $targetDir  = Split-Path -Parent $targetPath

        try {
            $remoteBytes = Get-RemoteBytes -Url $url
        }
        catch {
            Write-Log "Download fehlgeschlagen: $($entry.Source) - $($_.Exception.Message)" -Level ERROR
            $failed++
            continue
        }

        $remoteHash = Get-Sha256 -Bytes $remoteBytes

        if (Test-Path -LiteralPath $targetPath) {
            $localHash = Get-Sha256 -Bytes ([System.IO.File]::ReadAllBytes($targetPath))
            if ($localHash -eq $remoteHash) {
                Write-Log "unveraendert: $($entry.Target)"
                continue
            }
        }
        elseif (-not (Test-Path -LiteralPath $targetDir)) {
            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            Write-Log "Ordner angelegt: $targetDir"
        }

        try {
            [System.IO.File]::WriteAllBytes($targetPath, $remoteBytes)
            Write-Log "aktualisiert: $($entry.Target)" -Level CHANGE
            $changed++
            [void]$touchedDirs.Add($targetDir)
        }
        catch {
            Write-Log "Schreiben fehlgeschlagen: $targetPath - $($_.Exception.Message)" -Level ERROR
            $failed++
        }
    }

    foreach ($stale in $StaleFiles) {
        $stalePath = Join-Path $AllplanUsr $stale
        if (-not (Test-Path -LiteralPath $stalePath)) { continue }

        if ($RemoveStale) {
            try {
                Remove-Item -LiteralPath $stalePath -Force
                Write-Log "veraltete Datei entfernt: $stale" -Level CHANGE
                [void]$touchedDirs.Add((Split-Path -Parent $stalePath))
            }
            catch {
                Write-Log "Loeschen fehlgeschlagen: $stalePath - $($_.Exception.Message)" -Level ERROR
                $failed++
            }
        }
        else {
            Write-Log ("Veraltete Datei vorhanden: $stale - sie kollidiert mit dem Paketordner " +
                       "und verhindert den Import. Einmal mit -RemoveStale ausfuehren.") -Level WARN
        }
    }

    foreach ($dir in $touchedDirs) {
        Clear-PyCache -Directory $dir
    }

    if ($changed -gt 0) {
        Write-Log "$changed Datei(en) aktualisiert - Allplan neu starten bzw. Palette neu laden." -Level CHANGE
    }

    return $failed
}


function Install-SyncTask {
    if (-not (Get-Command Register-ScheduledTask -ErrorAction SilentlyContinue)) {
        throw 'Das ScheduledTasks-Modul ist auf diesem System nicht verfuegbar.'
    }

    $scriptPath = $PSCommandPath
    $logPath    = Join-Path $env:LOCALAPPDATA 'AllplanSlabReinforcementSync\sync.log'

    $arguments = @(
        '-NoProfile'
        '-ExecutionPolicy Bypass'
        '-WindowStyle Hidden'
        "-File `"$scriptPath`""
        "-AllplanUsr `"$AllplanUsr`""
        "-Branch `"$Branch`""
        "-Repo `"$Repo`""
        "-LogFile `"$logPath`""
        '-RemoveStale'
        '-Quiet'
    ) -join ' '

    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments

    $atLogon = New-ScheduledTaskTrigger -AtLogOn
    $repeat  = New-ScheduledTaskTrigger -Once -At (Get-Date) `
                   -RepetitionInterval (New-TimeSpan -Minutes 10) `
                   -RepetitionDuration ([TimeSpan]::MaxValue)

    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
                                             -DontStopIfGoingOnBatteries `
                                             -StartWhenAvailable `
                                             -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

    Register-ScheduledTask -TaskName $TaskName `
                           -Action $action `
                           -Trigger @($atLogon, $repeat) `
                           -Settings $settings `
                           -Description 'Synchronisiert die SlabReinforcement-Dateien aus GitHub nach Allplan.' `
                           -Force | Out-Null

    Write-Log "Geplante Aufgabe '$TaskName' registriert (bei Anmeldung + alle 10 Minuten)." -Level CHANGE
    Write-Log "Protokoll: $logPath"
}


function Uninstall-SyncTask {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Log "Geplante Aufgabe '$TaskName' entfernt." -Level CHANGE
    }
    else {
        Write-Log "Keine geplante Aufgabe '$TaskName' gefunden."
    }
}


# --- Ablauf ---------------------------------------------------------------

if ($Install -and $Uninstall) {
    throw '-Install und -Uninstall schliessen sich gegenseitig aus.'
}

if ($Uninstall) {
    Uninstall-SyncTask
    return
}

if ($Install) {
    Install-SyncTask
    Write-Log 'Fuehre einen ersten Sync aus ...'
}

if (-not (Test-Path -LiteralPath $AllplanUsr)) {
    Write-Log "Zielverzeichnis nicht erreichbar: $AllplanUsr (Netzlaufwerk verbunden?)" -Level ERROR
    exit 2
}

Write-Log "Sync $Repo@$Branch -> $AllplanUsr"

if ($IntervalSeconds -gt 0) {
    Write-Log "Dauerbetrieb: Pruefung alle $IntervalSeconds Sekunden (Abbruch mit Strg+C)."
    while ($true) {
        try {
            [void](Invoke-SyncPass)
        }
        catch {
            Write-Log "Durchlauf abgebrochen: $($_.Exception.Message)" -Level ERROR
        }
        Start-Sleep -Seconds $IntervalSeconds
    }
}

$failures = @(Invoke-SyncPass)[-1]
exit ([int]($failures -gt 0))
