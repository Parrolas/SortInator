[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$CandidateZip,
    [Parameter(Mandatory = $true)][string]$CandidateVersion,
    [string]$LegacyTag = "v0.6.1",
    [string]$LegacyZipName = "Organizador-0.6.1-windows-x64.zip",
    [string]$Repo = "Parrolas/organizador",
    [string]$SandboxRoot = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { $Python = "python" }

$CandidateZip = (Resolve-Path -LiteralPath $CandidateZip).Path
if ([string]::IsNullOrWhiteSpace($SandboxRoot)) {
    $SandboxRoot = [System.IO.Path]::GetTempPath().TrimEnd([System.IO.Path]::DirectorySeparatorChar)
}
$SandboxRoot = (Resolve-Path -LiteralPath $SandboxRoot).Path
if ([System.IO.Path]::GetPathRoot($SandboxRoot) -eq $SandboxRoot) {
    throw "Refusing to use a filesystem root as the sandbox root"
}
$RunId = [guid]::NewGuid().ToString("N")
$Sandbox = Join-Path $SandboxRoot ("Organizador-E2E-Jose-c-pct-" + $RunId)
if (-not $Sandbox.StartsWith($SandboxRoot)) { throw "Refusing to escape the sandbox root" }

$Install = Join-Path $Sandbox "install\Organizador"
$LegacySrc = Join-Path $Sandbox "legacy-src"
$FirstData = Join-Path $Sandbox "data-first"
$SmokeData = Join-Path $Sandbox "data-smoke"
$FakeLocal = Join-Path $Sandbox "fake-local"
$FakeRoaming = Join-Path $Sandbox "fake-roaming"
$Evidence = Join-Path $Sandbox "evidence.log"

$OldExe = $null

function Write-Evidence([string]$Message) {
    $Line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message
    Write-Host $Line
    Add-Content -LiteralPath $Evidence -Value $Line -Encoding UTF8
}

function Fail([string]$Message) {
    Write-Evidence "FAIL: $Message"
    throw $Message
}

function Get-ProductVersion([string]$ExePath) {
    return (Get-Item -LiteralPath $ExePath).VersionInfo.ProductVersion
}

function Get-SandboxProcessIds {
    $Prefix = $Sandbox + [System.IO.Path]::DirectorySeparatorChar
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($Prefix, [StringComparison]::OrdinalIgnoreCase) } |
        Select-Object -ExpandProperty ProcessId
}

function Stop-SandboxProcesses {
    foreach ($Id in (Get-SandboxProcessIds)) {
        try { Stop-Process -Id $Id -Force -ErrorAction SilentlyContinue } catch { }
    }
}

function Wait-ForCondition([scriptblock]$Predicate, [int]$TimeoutSeconds, [string]$What) {
    $Deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $Deadline) {
        if (& $Predicate) { return }
        Start-Sleep -Milliseconds 250
    }
    Fail "Timed out waiting for: $What"
}

function Invoke-LegacyPython([string]$Name, [string]$Code, [hashtable]$ExtraEnv) {
    # PowerShell 5.1 strips embedded double quotes from native arguments, so the
    # driver is staged as a file instead of passed through -c (works on 5.1 and 7).
    $DriverDir = Join-Path $Sandbox "drivers"
    New-Item -ItemType Directory -Path $DriverDir -Force | Out-Null
    $DriverPath = Join-Path $DriverDir ("$Name.py")
    [System.IO.File]::WriteAllText(
        $DriverPath, $Code, (New-Object System.Text.UTF8Encoding($false))
    )
    $Names = @("PYTHONPATH", "PYTHONNOUSERSITE") + @($ExtraEnv.Keys)
    $Previous = @{}
    foreach ($Key in $Names) { $Previous[$Key] = [System.Environment]::GetEnvironmentVariable($Key) }
    try {
        # git archive keeps the src/ layout, so the import root is one level down.
        [System.Environment]::SetEnvironmentVariable(
            "PYTHONPATH", (Join-Path $LegacySrc "src")
        )
        [System.Environment]::SetEnvironmentVariable("PYTHONNOUSERSITE", "1")
        [System.Environment]::SetEnvironmentVariable("ORGANIZADOR_E2E_SANDBOX", $Sandbox)
        foreach ($Key in $ExtraEnv.Keys) { [System.Environment]::SetEnvironmentVariable($Key, $ExtraEnv[$Key]) }
        $Output = & $Python $DriverPath 2>&1
        if ($LASTEXITCODE -ne 0) { Fail ("Legacy python driver $Name failed:`n" + ($Output -join "`n")) }
        return ($Output -join "`n")
    }
    finally {
        foreach ($Key in $Names) { [System.Environment]::SetEnvironmentVariable($Key, $Previous[$Key]) }
    }
}

$ProvenanceCode = @'
import os, sys
sys.path.insert(0, os.path.join(os.environ["ORGANIZADOR_E2E_SANDBOX"], "legacy-src", "src"))
from organizador import updater as L, __version__
print(L.__file__)
print(__version__)
'@

$CorruptCode = @'
import os, sys
sys.path.insert(0, os.environ["ORGANIZADOR_E2E_SANDBOX"] + "\\legacy-src\\src")
from pathlib import Path
from organizador import updater as L
sandbox = Path(os.environ["ORGANIZADOR_E2E_SANDBOX"])
app = sandbox / "install" / "Organizador"
corrupt = sandbox / "corrupt" / "corrupt.zip"
sidecar = sandbox / "corrupt" / "corrupt.zip.sha256"
try:
    z = L.download_and_verify(corrupt.as_uri(), sidecar.as_uri(), sandbox / "corrupt-dl")
    L.extract_to_staging(z, L.staging_directory(app))
    print("UNEXPECTED-SUCCESS")
except Exception as exc:
    print("EXPECTED-FAILURE: " + type(exc).__name__)
'@

$PrepareCode = @'
import os, sys
sys.path.insert(0, os.environ["ORGANIZADOR_E2E_SANDBOX"] + "\\legacy-src\\src")
from pathlib import Path
from organizador import updater as L
sandbox = Path(os.environ["ORGANIZADOR_E2E_SANDBOX"])
app = sandbox / "install" / "Organizador"
z = L.download_and_verify(os.environ["ORGANIZADOR_E2E_ZIP"], os.environ["ORGANIZADOR_E2E_SHA"], sandbox / "dl")
staging = L.extract_to_staging(z, L.staging_directory(app))
script = L.write_swap_script(app, staging)
print("SCRIPT:" + str(script))
'@

$LaunchCode = @'
import os, sys
sys.path.insert(0, os.environ["ORGANIZADOR_E2E_SANDBOX"] + "\\legacy-src\\src")
from pathlib import Path
from organizador import updater as L
L.launch_swap(Path(os.environ["ORGANIZADOR_E2E_SCRIPT"]))
print("LAUNCHED")
'@

$SentinelCode = @'
import os, sqlite3
sandbox = os.environ["ORGANIZADOR_E2E_SANDBOX"]
action = os.environ.get("ORGANIZADOR_E2E_SENTINEL_ACTION", "")
db = os.path.join(sandbox, "data-first", "organizador.db")
connection = sqlite3.connect(db)
try:
    if action == "setup":
        connection.execute("DROP TABLE IF EXISTS e2e_sentinel")
        connection.execute("CREATE TABLE e2e_sentinel(value TEXT)")
        connection.execute("INSERT INTO e2e_sentinel VALUES ('antes')")
        connection.commit()
    elif action == "drop":
        connection.execute("DROP TABLE e2e_sentinel")
        connection.commit()
    elif action == "check":
        row = connection.execute("SELECT value FROM e2e_sentinel").fetchone()
        print("SENTINEL:" + (row[0] if row else "missing"))
finally:
    connection.close()
'@

try {
    New-Item -ItemType Directory -Path $Sandbox | Out-Null
    New-Item -ItemType Directory -Path (Split-Path -Parent $Evidence) -Force | Out-Null
    New-Item -ItemType File -Path $Evidence -Force | Out-Null
    Write-Evidence "Sandbox: $Sandbox"
    Write-Evidence "Candidate: $CandidateZip ($CandidateVersion)"

    if ($CandidateVersion -notmatch '^\d+\.\d+\.\d+$') { Fail "Candidate version is not MAJOR.MINOR.PATCH" }

    # 1. Candidate archive layout gate.
    Write-Evidence "Checking candidate archive layout"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Archive = [System.IO.Compression.ZipFile]::OpenRead($CandidateZip)
    try {
        # Compress-Archive stores backslashes; the extractor normalises them.
        $Names = @($Archive.Entries | ForEach-Object { $_.FullName.Replace("\", "/") })
    }
    finally {
        $Archive.Dispose()
    }
    foreach ($Required in @("Organizador.exe", "_internal/", "update-manifest.json")) {
        if (-not ($Names | Where-Object { $_ -eq $Required -or $_.StartsWith($Required) })) {
            Fail "Candidate archive is missing $Required"
        }
    }
    if ($Names | Where-Object { $_ -like "*/Organizador.exe" }) {
        Fail "Candidate archive must stay flat (exe at the root)"
    }

    # 2. Public legacy assets, verified against their published checksum.
    Write-Evidence "Downloading public $LegacyTag assets"
    $LegacyZip = Join-Path $Sandbox "legacy.zip"
    $LegacySha = Join-Path $Sandbox "legacy.zip.sha256"
    Invoke-WebRequest -Uri "https://github.com/$Repo/releases/download/$LegacyTag/$LegacyZipName" -OutFile $LegacyZip
    Invoke-WebRequest -Uri "https://github.com/$Repo/releases/download/$LegacyTag/$LegacyZipName.sha256" -OutFile $LegacySha
    $ExpectedHash = ((Get-Content -LiteralPath $LegacySha -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
    $ActualHash = (Get-FileHash -LiteralPath $LegacyZip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ExpectedHash -ne $ActualHash) { Fail "Public legacy checksum mismatch" }
    Write-Evidence "Legacy assets verified"

    # 3. Install the legacy build and extract its exact updater source.
    New-Item -ItemType Directory -Path $Install | Out-Null
    Expand-Archive -LiteralPath $LegacyZip -DestinationPath $Install -Force
    if (-not (Test-Path -LiteralPath (Join-Path $Install "Organizador.exe"))) {
        Fail "Legacy install has no exe"
    }
    if ((Get-ProductVersion (Join-Path $Install "Organizador.exe")) -ne "0.6.1") {
        Fail "Legacy install is not 0.6.1"
    }
    New-Item -ItemType Directory -Path $LegacySrc | Out-Null
    # PowerShell 5.1 corrupts binary pipes, so stage through a file (works on 5.1 and 7).
    $LegacyTar = Join-Path $Sandbox "legacy-src.tar"
    & git -C $Root archive "--output=$LegacyTar" $LegacyTag src
    if ($LASTEXITCODE -ne 0) { Fail "Could not extract $LegacyTag sources" }
    & tar -xf $LegacyTar -C $LegacySrc
    if ($LASTEXITCODE -ne 0) { Fail "Could not unpack $LegacyTag sources" }
    Remove-Item -LiteralPath $LegacyTar -Force -ErrorAction SilentlyContinue
    $Provenance = Invoke-LegacyPython "provenance" $ProvenanceCode @{}
    Write-Evidence ("Legacy provenance: " + ($Provenance -replace "`n", " / "))
    if ($Provenance -notlike "*legacy-src*" -or $Provenance -notlike "*0.6.1*") {
        Fail "Legacy python did not resolve to the isolated $LegacyTag sources"
    }

    # 4. The installed legacy exe launches cleanly on its own.
    Write-Evidence "Legacy smoke run"
    $Smoke = Start-Process -FilePath (Join-Path $Install "Organizador.exe") -ArgumentList ('--smoke-test --data-dir "' + $FirstData + '"') -WindowStyle Hidden -Wait -PassThru
    if ($Smoke.ExitCode -ne 0) { Fail "Legacy smoke run failed" }

    # 5. A corrupt payload must never reach the swap.
    Write-Evidence "Corrupt-payload gate"
    $CorruptDir = Join-Path $Sandbox "corrupt"
    New-Item -ItemType Directory -Path $CorruptDir | Out-Null
    $CorruptZip = Join-Path $CorruptDir "corrupt.zip"
    [System.IO.File]::WriteAllBytes($CorruptZip, (New-Object byte[] 64))
    $CorruptHash = (Get-FileHash -LiteralPath $CorruptZip -Algorithm SHA256).Hash.ToLowerInvariant()
    [System.IO.File]::WriteAllText(
        (Join-Path $CorruptDir "corrupt.zip.sha256"),
        "$CorruptHash  corrupt.zip`n",
        (New-Object System.Text.UTF8Encoding($false))
    )
    $CorruptOut = Invoke-LegacyPython "corrupt" $CorruptCode @{}
    Write-Evidence $CorruptOut
    if ($CorruptOut -notlike "*EXPECTED-FAILURE*") { Fail "Corrupt payload reached the swap" }
    if (Test-Path -LiteralPath (Join-Path $Sandbox "install\organizador-update.cmd")) {
        Fail "Corrupt payload left a swap script behind"
    }

    # 6. Happy path: old exe exits on its own inside the legacy 2s wait, then swap.
    Write-Evidence "Starting legacy exe (self-exiting smoke) and preparing the legacy swap"
    $CandidateSha = "$CandidateZip.sha256"
    if (-not (Test-Path -LiteralPath $CandidateSha)) { Fail "Candidate checksum sidecar is missing" }
    $OldExe = Start-Process -FilePath (Join-Path $Install "Organizador.exe") -ArgumentList ('--smoke-test --data-dir "' + $FirstData + '"') -WindowStyle Hidden -PassThru
    $PrepareOut = Invoke-LegacyPython "prepare" $PrepareCode @{
        "ORGANIZADOR_E2E_ZIP" = ([System.Uri]$CandidateZip).AbsoluteUri
        "ORGANIZADOR_E2E_SHA" = ([System.Uri]$CandidateSha).AbsoluteUri
    }
    $ScriptLine = ($PrepareOut -split "`n" | Where-Object { $_ -like "SCRIPT:*" } | Select-Object -First 1)
    if (-not $ScriptLine) { Fail "Legacy preparation produced no swap script" }
    $SwapScript = $ScriptLine.Substring(7)
    Write-Evidence "Swap script ready"

    Wait-ForCondition { $OldExe.HasExited } 15 "legacy exe self-exit"
    # The legacy helper relaunches with a bare --background, so redirect the
    # well-known profile roots: every descendant (helper, candidate) inherits
    # the sandbox and the real %LOCALAPPDATA%\Organizador stays untouched.
    New-Item -ItemType Directory -Path (Join-Path $FakeLocal "Organizador") -Force | Out-Null
    [System.IO.File]::WriteAllText(
        (Join-Path $FakeLocal "Organizador\sentinel.txt"),
        "do not touch`n",
        (New-Object System.Text.UTF8Encoding($false))
    )
    $SavedLocal = $env:LOCALAPPDATA
    $SavedRoaming = $env:APPDATA
    $SavedIntegration = $env:ORGANIZADOR_DISABLE_WINDOWS_INTEGRATION
    $env:LOCALAPPDATA = $FakeLocal
    $env:APPDATA = $FakeRoaming
    $env:ORGANIZADOR_DISABLE_WINDOWS_INTEGRATION = "1"
    try {
        $LaunchOut = Invoke-LegacyPython "launch" $LaunchCode @{ "ORGANIZADOR_E2E_SCRIPT" = $SwapScript }
    }
    finally {
        $env:LOCALAPPDATA = $SavedLocal
        $env:APPDATA = $SavedRoaming
        $env:ORGANIZADOR_DISABLE_WINDOWS_INTEGRATION = $SavedIntegration
    }
    Write-Evidence $LaunchOut

    Wait-ForCondition { (Get-ProductVersion (Join-Path $Install "Organizador.exe")) -eq $CandidateVersion } 60 "active exe becoming $CandidateVersion"
    $OldDir = Join-Path $Sandbox "install\Organizador.old"
    Wait-ForCondition { Test-Path -LiteralPath (Join-Path $OldDir "Organizador.exe") } 20 "rollback folder"
    if ((Get-ProductVersion (Join-Path $OldDir "Organizador.exe")) -ne "0.6.1") {
        Fail "Rollback folder is not 0.6.1"
    }
    if (Test-Path -LiteralPath (Join-Path $Sandbox "install\Organizador.update")) {
        Fail "Staging directory was left behind"
    }
    Write-Evidence "Swap complete: active=$CandidateVersion rollback=0.6.1"

    # 7. The relaunched candidate must come from the new folder, then be smoke-tested.
    Wait-ForCondition { @(Get-SandboxProcessIds).Count -gt 0 } 60 "relaunched candidate process"
    $NewPids = @(Get-SandboxProcessIds)
    Write-Evidence ("Relaunched PIDs: " + ($NewPids -join ","))
    Stop-SandboxProcesses
    $Deadline = [DateTime]::UtcNow.AddSeconds(15)
    while ([DateTime]::UtcNow -lt $Deadline) {
        $Alive = @($NewPids | Where-Object {
            try { [void](Get-Process -Id $_ -ErrorAction Stop); $true } catch { $false }
        })
        if ($Alive.Count -eq 0) { break }
        Write-Evidence ("Waiting for PIDs: " + ($Alive -join ","))
        Start-Sleep -Milliseconds 1000
    }
    $Alive = @($NewPids | Where-Object {
        try { [void](Get-Process -Id $_ -ErrorAction Stop); $true } catch { $false }
    })
    if ($Alive.Count -gt 0) { Fail ("Candidate did not shut down: " + ($Alive -join ",")) }

    Write-Evidence "Candidate smoke run"
    $CandidateSmoke = Start-Process -FilePath (Join-Path $Install "Organizador.exe") -ArgumentList ('--smoke-test --data-dir "' + $SmokeData + '"') -WindowStyle Hidden -Wait -PassThru
    if ($CandidateSmoke.ExitCode -ne 0) { Fail "Candidate smoke run failed" }

    $Sentinel = Get-Content -LiteralPath (Join-Path $FakeLocal "Organizador\sentinel.txt") -Raw
    if ($Sentinel.Trim() -ne "do not touch") { Fail "Candidate disturbed the sandboxed profile" }

    # 8. On-demand backup and staged restore through the candidate CLI.
    Write-Evidence "Backup and restore gate"
    $FirstDatabase = Join-Path $FirstData "organizador.db"
    if (-not (Test-Path -LiteralPath $FirstDatabase)) { Fail "Expected profile database is missing" }
    $BackupExport = Join-Path $Sandbox "backup-export"
    New-Item -ItemType Directory -Path $BackupExport -Force | Out-Null
    $CandidateExe = Join-Path $Install "Organizador.exe"
    Invoke-LegacyPython "sentinel" $SentinelCode @{ "ORGANIZADOR_E2E_SENTINEL_ACTION" = "setup" } | Out-Null

    $BackupRun = Start-Process -FilePath $CandidateExe -ArgumentList ('--backup-now "' + $BackupExport + '" --data-dir "' + $FirstData + '"') -WindowStyle Hidden -Wait -PassThru
    if ($BackupRun.ExitCode -ne 0) { Fail ("Backup failed with exit code " + $BackupRun.ExitCode) }
    $BackupZip = Get-ChildItem -LiteralPath $BackupExport -Filter "*.zip" | Select-Object -First 1
    if ($null -eq $BackupZip) { Fail "Backup produced no archive" }
    Write-Evidence ("Backup archive: " + $BackupZip.Name)

    Invoke-LegacyPython "sentinel" $SentinelCode @{ "ORGANIZADOR_E2E_SENTINEL_ACTION" = "drop" } | Out-Null
    $RestoreRun = Start-Process -FilePath $CandidateExe -ArgumentList ('--restore-from "' + $BackupZip.FullName + '" --data-dir "' + $FirstData + '"') -WindowStyle Hidden -Wait -PassThru
    if ($RestoreRun.ExitCode -ne 0) { Fail ("Restore staging failed with exit code " + $RestoreRun.ExitCode) }
    if (-not (Test-Path -LiteralPath (Join-Path $FirstData "restore-request.json"))) {
        Fail "Restore request was not staged"
    }

    $RestoreSmoke = Start-Process -FilePath $CandidateExe -ArgumentList ('--smoke-test --data-dir "' + $FirstData + '"') -WindowStyle Hidden -Wait -PassThru
    if ($RestoreSmoke.ExitCode -ne 0) { Fail "Restore startup run failed" }

    $SentinelCheck = Invoke-LegacyPython "sentinel" $SentinelCode @{ "ORGANIZADOR_E2E_SENTINEL_ACTION" = "check" }
    if (($SentinelCheck -join "`n") -notmatch "SENTINEL:antes") {
        Fail "Restore did not recover the sentinel data"
    }
    $PreRestore = @(Get-ChildItem -LiteralPath (Join-Path $FirstData "backups") -Directory -Filter "pre_restore-*" -ErrorAction SilentlyContinue)
    if ($PreRestore.Count -lt 1) { Fail "Restore left no pre-restore snapshot" }
    if (Test-Path -LiteralPath (Join-Path $FirstData "restore-request.json")) {
        Fail "Restore request was not consumed"
    }
    Write-Evidence "Backup and restore verified"

    Write-Evidence "E2E PASS: $LegacyTag -> $CandidateVersion"
}
catch {
    if (Test-Path -LiteralPath $Evidence) {
        $Kept = Join-Path $Root ("update-e2e-evidence-" + $RunId + ".log")
        Copy-Item -LiteralPath $Evidence -Destination $Kept -Force -ErrorAction SilentlyContinue
        Write-Host "Evidence preserved at: $Kept"
    }
    throw
}
finally {
    try { Stop-SandboxProcesses } catch { }
    if ($OldExe -and -not $OldExe.HasExited) {
        try { Stop-Process -Id $OldExe.Id -Force -ErrorAction SilentlyContinue } catch { }
    }
    if ((Test-Path -LiteralPath $Sandbox) -and @(Get-SandboxProcessIds).Count -eq 0) {
        Remove-Item -LiteralPath $Sandbox -Recurse -Force -ErrorAction SilentlyContinue
    }
    elseif (Test-Path -LiteralPath $Sandbox) {
        Write-Host "Keeping sandbox (processes still running): $Sandbox"
    }
}
