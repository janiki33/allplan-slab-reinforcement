<#
.SYNOPSIS
    Synchronisiert die SlabReinforcement-Dateien aus GitHub in das lokale
    Allplan-Benutzerverzeichnis.

.DESCRIPTION
    Spiegelt zwei Ordner aus dem Repository:

        PythonPartsScripts/SlabReinforcement  ->  <AllplanUsr>\PythonPartsScripts\SlabReinforcement
        Library/SlabReinforcement             ->  <AllplanUsr>\Library\SlabReinforcement

    Welche Dateien darin liegen, fragt das Skript bei jedem Lauf ueber die
    GitHub-API ab - es gibt also keine fest verdrahtete Dateiliste, die bei
    einer Umbenennung veraltet. Verglichen wird ueber den Git-Blob-Hash;
    heruntergeladen wird nur, was sich tatsaechlich unterscheidet.

    GitHub ist die Quelle der Wahrheit: lokale Aenderungen an den gespiegelten
    Dateien werden ueberschrieben, und lokale .py/.pyp-Dateien, die es im
    Repository nicht (mehr) gibt, werden geloescht - genau das faengt
    Umbenennungen ab, die sonst als Karteileiche den Import blockieren.
    Mit -KeepExtraFiles unterbleibt das Loeschen.

    Bei jeder Aenderung wird zusaetzlich __pycache__ geleert, damit Allplan
    die Module wirklich neu laedt.

.PARAMETER AllplanUsr
    Wurzel des Allplan-Benutzerverzeichnisses.

.PARAMETER Branch
    Zu synchronisierender Git-Branch.

.PARAMETER IntervalSeconds
    Wenn gesetzt, laeuft das Skript dauerhaft und prueft im angegebenen Abstand
    erneut. Ohne diesen Parameter laeuft es genau einmal durch.

.PARAMETER KeepExtraFiles
    Lokale .py/.pyp-Dateien behalten, die es im Repository nicht gibt.

.PARAMETER Token
    Optionales GitHub-Token. Nur noetig, wenn das Limit fuer nicht
    angemeldete API-Zugriffe (60 pro Stunde und IP) knapp wird.

.PARAMETER Install
    Registriert eine geplante Aufgabe, die den Abgleich bei der Anmeldung und
    danach alle 10 Minuten ausfuehrt.

.PARAMETER Uninstall
    Entfernt die mit -Install angelegte geplante Aufgabe wieder.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Sync-SlabReinforcement.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Sync-SlabReinforcement.ps1 -Install
#>

[CmdletBinding()]
param(
    [string] $AllplanUsr      = 'J:\Allplan\Usr\Janosch',
    [string] $Branch          = 'main',
    [string] $Repo            = 'janiki33/allplan-slab-reinforcement',
    [int]    $IntervalSeconds = 0,
    [switch] $KeepExtraFiles,
    [string] $Token,
    [switch] $Install,
    [switch] $Uninstall,
    [string] $LogFile,
    [switch] $Quiet,
    # Nur noch aus Kompatibilitaet: das Entfernen veralteter Dateien ist
    # inzwischen Standardverhalten des Abgleichs.
    [switch] $RemoveStale
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# PowerShell 5.1 verhandelt sonst teilweise noch TLS 1.0 - GitHub lehnt das ab.
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$TaskName = 'AllplanSlabReinforcementSync'

# Wird beim Start protokolliert und von Update-SlabReinforcement.cmd geprueft,
# damit nie unbemerkt eine veraltete Fassung aus einem Cache laeuft.
$ScriptVersion = 2

# Gespiegelte Ordner: Pfad im Repository -> Pfad relativ zu $AllplanUsr
$SyncDirs = @(
    @{ Source = 'PythonPartsScripts/SlabReinforcement'; Target = 'PythonPartsScripts\SlabReinforcement' }
    @{ Source = 'Library/SlabReinforcement';            Target = 'Library\SlabReinforcement' }
)

# Nur diese Dateitypen werden gespiegelt und ggf. lokal aufgeraeumt.
$SyncedExtensions = @('.py', '.pyp')


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
            # Ein nicht schreibbares Logfile darf den Abgleich nicht abbrechen.
        }
    }
}


function Get-RequestHeaders {
    $headers = @{
        'Cache-Control' = 'no-cache'
        'Pragma'        = 'no-cache'
        'User-Agent'    = 'AllplanSlabReinforcementSync'
    }
    if ($Token) {
        $headers['Authorization'] = "Bearer $Token"
    }
    return $headers
}


function Get-GitBlobSha {
    <# Git-Blob-Hash einer Datei: sha1("blob <laenge>\0" + inhalt).
       Damit laesst sich direkt gegen das sha-Feld der GitHub-API vergleichen. #>
    param([Parameter(Mandatory)][string] $Path)

    $bytes  = [System.IO.File]::ReadAllBytes($Path)
    $header = [System.Text.Encoding]::ASCII.GetBytes('blob ' + $bytes.Length + [char]0)

    $buffer = New-Object byte[] ($header.Length + $bytes.Length)
    [Array]::Copy($header, 0, $buffer, 0, $header.Length)
    [Array]::Copy($bytes, 0, $buffer, $header.Length, $bytes.Length)

    $sha1 = [System.Security.Cryptography.SHA1]::Create()
    try {
        return [BitConverter]::ToString($sha1.ComputeHash($buffer)).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha1.Dispose()
    }
}


function Get-RemoteListing {
    <# Verzeichnisinhalt eines Repository-Ordners ueber die GitHub-API.
       Der Branch steht als Query-Parameter, damit Schraegstriche im
       Branchnamen (claude/...) nicht den Pfad zerlegen. #>
    param([Parameter(Mandatory)][string] $Path)

    $uri = 'https://api.github.com/repos/{0}/contents/{1}?ref={2}' -f `
           $Repo, $Path, [uri]::EscapeDataString($Branch)

    $entries = Invoke-RestMethod -Uri $uri -Headers (Get-RequestHeaders) -TimeoutSec 60

    return @($entries) |
        Where-Object { $_.type -eq 'file' } |
        ForEach-Object {
            [pscustomobject]@{
                Name        = $_.name
                Sha         = $_.sha
                DownloadUrl = $_.download_url
            }
        }
}


function Save-RemoteFile {
    param(
        [Parameter(Mandatory)][string] $Url,
        [Parameter(Mandatory)][string] $Destination
    )

    # Erst in eine Nebendatei laden, dann umbenennen: bricht der Download ab,
    # bleibt die bisherige Fassung unangetastet.
    $temp = "$Destination.download"
    try {
        Invoke-WebRequest -Uri $Url -Headers (Get-RequestHeaders) `
                          -UseBasicParsing -TimeoutSec 60 -OutFile $temp | Out-Null

        if ((Get-Item -LiteralPath $temp).Length -eq 0) {
            throw "Leere Antwort von $Url"
        }

        Move-Item -LiteralPath $temp -Destination $Destination -Force
    }
    catch {
        Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
        throw
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


function Sync-Directory {
    param([Parameter(Mandatory)][hashtable] $Entry)

    $result    = [pscustomobject]@{ Changed = 0; Failed = 0 }
    $targetDir = Join-Path $AllplanUsr $Entry.Target

    try {
        $remoteFiles = @(Get-RemoteListing -Path $Entry.Source)
    }
    catch {
        Write-Log "Verzeichnis $($Entry.Source) nicht abrufbar: $($_.Exception.Message)" -Level ERROR
        $result.Failed++
        return $result
    }

    $remoteFiles = @($remoteFiles | Where-Object { $SyncedExtensions -contains [System.IO.Path]::GetExtension($_.Name) })

    if ($remoteFiles.Count -eq 0) {
        Write-Log "$($Entry.Source) enthaelt keine abzugleichenden Dateien - uebersprungen." -Level WARN
        return $result
    }

    if (-not (Test-Path -LiteralPath $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        Write-Log "Ordner angelegt: $targetDir"
    }

    foreach ($file in $remoteFiles) {
        $targetPath = Join-Path $targetDir $file.Name

        if (Test-Path -LiteralPath $targetPath) {
            if ((Get-GitBlobSha -Path $targetPath) -eq $file.Sha) {
                Write-Log "unveraendert: $($Entry.Target)\$($file.Name)"
                continue
            }
        }

        try {
            Save-RemoteFile -Url $file.DownloadUrl -Destination $targetPath
            Write-Log "aktualisiert: $($Entry.Target)\$($file.Name)" -Level CHANGE
            $result.Changed++
        }
        catch {
            Write-Log "Abgleich fehlgeschlagen: $($Entry.Target)\$($file.Name) - $($_.Exception.Message)" -Level ERROR
            $result.Failed++
        }
    }

    # Lokale Karteileichen entfernen - dank vollstaendiger Verzeichnisliste
    # sind das genau die Dateien, die im Repository umbenannt oder geloescht
    # wurden.
    $remoteNames = @($remoteFiles | ForEach-Object { $_.Name })

    foreach ($local in @(Get-ChildItem -LiteralPath $targetDir -File -ErrorAction SilentlyContinue)) {
        if ($SyncedExtensions -notcontains $local.Extension) { continue }
        if ($remoteNames -contains $local.Name)              { continue }

        if ($KeepExtraFiles) {
            Write-Log ("Nicht im Repository: $($Entry.Target)\$($local.Name) - bleibt liegen " +
                       "(-KeepExtraFiles gesetzt), kann den Import stoeren.") -Level WARN
            continue
        }

        try {
            Remove-Item -LiteralPath $local.FullName -Force
            Write-Log "entfernt (nicht mehr im Repository): $($Entry.Target)\$($local.Name)" -Level CHANGE
            $result.Changed++
        }
        catch {
            Write-Log "Loeschen fehlgeschlagen: $($local.FullName) - $($_.Exception.Message)" -Level ERROR
            $result.Failed++
        }
    }

    if ($result.Changed -gt 0) {
        Clear-PyCache -Directory $targetDir
    }

    return $result
}


function Invoke-SyncPass {
    $changed = 0
    $failed  = 0

    foreach ($entry in $SyncDirs) {
        $r = Sync-Directory -Entry $entry
        $changed += $r.Changed
        $failed  += $r.Failed
    }

    if ($changed -gt 0) {
        Write-Log "$changed Aenderung(en) uebernommen - Allplan neu starten." -Level CHANGE
    }
    elseif ($failed -eq 0) {
        Write-Log 'Alles bereits auf dem Stand von GitHub.'
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
    Write-Log 'Fuehre einen ersten Abgleich aus ...'
}

if (-not (Test-Path -LiteralPath $AllplanUsr)) {
    Write-Log "Zielverzeichnis nicht erreichbar: $AllplanUsr (Netzlaufwerk verbunden?)" -Level ERROR
    exit 2
}

Write-Log "Abgleich $Repo@$Branch -> $AllplanUsr (Skriptfassung $ScriptVersion)"

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
