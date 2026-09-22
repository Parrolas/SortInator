[CmdletBinding()]
param(
    [string]$OutputRoot = "",
    [string]$SigningCertificateThumbprint = "",
    [string]$SignTool = "signtool.exe",
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$EntryPoint = Join-Path $Root "src\organizador\main.py"
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $Root "artifacts"
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot = Join-Path $Root $OutputRoot
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$BuildRoot = Join-Path $OutputRoot "build"
$AssetRoot = Join-Path $BuildRoot "assets"
$Distribution = Join-Path $OutputRoot "SortInator"
$Executable = Join-Path $Distribution "SortInator.exe"
$VersionInfo = Join-Path $BuildRoot "version_info.txt"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Ambiente não encontrado. Executa primeiro .\scripts\setup.ps1"
}

$Version = (& $Python -c "from organizador import __version__; print(__version__)").Trim()
if ($LASTEXITCODE -ne 0 -or $Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Não foi possível obter uma versão MAJOR.MINOR.PATCH válida"
}

& $Python -m ruff check (Join-Path $Root "src") (Join-Path $Root "tests") (Join-Path $Root "scripts")
if ($LASTEXITCODE -ne 0) { throw "ruff falhou" }

& $Python -m ruff format --check (Join-Path $Root "src") (Join-Path $Root "tests") (Join-Path $Root "scripts")
if ($LASTEXITCODE -ne 0) { throw "ruff format falhou" }

& $Python -m mypy (Join-Path $Root "src\organizador")
if ($LASTEXITCODE -ne 0) { throw "mypy falhou" }

$env:QT_QPA_PLATFORM = "offscreen"
& $Python -m pytest (Join-Path $Root "tests")
if ($LASTEXITCODE -ne 0) { throw "pytest falhou" }
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue

& $Python (Join-Path $Root "scripts\generate_version_info.py") $VersionInfo
if ($LASTEXITCODE -ne 0) { throw "Não foi possível gerar os metadados de versão" }

& $Python (Join-Path $Root "scripts\generate_icon.py") --output-dir $AssetRoot
if ($LASTEXITCODE -ne 0) { throw "Não foi possível gerar o ícone da aplicação" }
$AppIcon = Join-Path $AssetRoot "icon.ico"
if (-not (Test-Path -LiteralPath $AppIcon)) { throw "Ícone em falta: $AppIcon" }

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --icon $AppIcon `
    --add-data ($AssetRoot + ";assets") `
    --noupx `
    --name "SortInator" `
    --paths (Join-Path $Root "src") `
    --hidden-import "watchdog.observers.winapi" `
    --version-file $VersionInfo `
    --specpath $BuildRoot `
    --workpath (Join-Path $BuildRoot "pyinstaller") `
    --distpath $OutputRoot `
    $EntryPoint
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }

if (-not (Test-Path -LiteralPath $Executable)) {
    throw "O executável esperado não foi criado: $Executable"
}

# Transitional: update helpers from releases before the rename launch a
# hardcoded Organizador.exe after swapping payloads. This hardlink keeps
# over-the-air updates from those versions working; it is removed once no
# such helper is in circulation.
$LegacyExecutable = Join-Path $Distribution "Organizador.exe"
Remove-Item -LiteralPath $LegacyExecutable -Force -ErrorAction SilentlyContinue
New-Item -ItemType HardLink -Path $LegacyExecutable -Target $Executable | Out-Null

if ($SigningCertificateThumbprint) {
    if ($SigningCertificateThumbprint -notmatch '^[0-9a-fA-F]{40}$') { throw "Invalid signing thumbprint" }
    & $SignTool sign /sha1 $SigningCertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $Executable
    if ($LASTEXITCODE -ne 0) { throw "Application signing failed" }
    & $SignTool verify /pa $Executable
    if ($LASTEXITCODE -ne 0) { throw "Application signature verification failed" }
}

$SmokeRoot = Join-Path $env:TEMP ("sortinator-smoke-" + [guid]::NewGuid().ToString("N"))
try {
    New-Item -ItemType Directory -Path $SmokeRoot | Out-Null
    $SmokeArguments = "--smoke-test --data-dir `"$SmokeRoot`""
    $SmokeProcess = Start-Process `
        -FilePath $Executable `
        -ArgumentList $SmokeArguments `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
    if ($SmokeProcess.ExitCode -ne 0) {
        throw "O executável não passou o arranque de teste"
    }
}
finally {
    if (Test-Path -LiteralPath $SmokeRoot) {
        Remove-Item -LiteralPath $SmokeRoot -Recurse -Force
    }
}

Copy-Item -LiteralPath (Join-Path $Root "LICENSE") -Destination $Distribution
Copy-Item -LiteralPath (Join-Path $Root "LICENSES") -Destination $Distribution -Recurse
& $Python (Join-Path $Root "scripts\collect_licenses.py") (Join-Path $Distribution "LICENSES")
if ($LASTEXITCODE -ne 0) { throw "Não foi possível recolher as licenças" }
$RequiredNotices = @(
    (Join-Path $Distribution "LICENSE"),
    (Join-Path $Distribution "LICENSES\GPL-3.0.txt"),
    (Join-Path $Distribution "LICENSES\LGPL-3.0.txt"),
    (Join-Path $Distribution "LICENSES\PYTHON-LICENSE.txt"),
    (Join-Path $Distribution "LICENSES\THIRD-PARTY-NOTICES.md")
)
foreach ($Notice in $RequiredNotices) {
    if (-not (Test-Path -LiteralPath $Notice)) {
        throw "Aviso de licença em falta: $Notice"
    }
}

$ManifestEncoding = New-Object System.Text.UTF8Encoding($false)
$ManifestJson = (@{ format = 1; version = $Version; executable = "SortInator.exe"; internal_directory = "_internal" } | ConvertTo-Json -Compress) + "`n"
[System.IO.File]::WriteAllText((Join-Path $Distribution "update-manifest.json"), $ManifestJson, $ManifestEncoding)
$ManifestCheck = Get-Content -LiteralPath (Join-Path $Distribution "update-manifest.json") -Raw | ConvertFrom-Json
if ($ManifestCheck.version -ne $Version) {
    throw "O manifesto da atualização não coincide com a versão"
}

$ManagedFiles = @(Get-ChildItem -LiteralPath $Distribution -Recurse -File | ForEach-Object {
    $_.FullName.Substring($Distribution.Length + 1)
}) + "runtime-files.txt"
[IO.File]::WriteAllLines((Join-Path $Distribution "runtime-files.txt"), $ManagedFiles, $ManifestEncoding)

$ReleaseDirectory = Join-Path $OutputRoot "releases"
New-Item -ItemType Directory -Path $ReleaseDirectory -Force | Out-Null
$ArchiveName = "SortInator-$Version-windows-x64.zip"
$Archive = Join-Path $ReleaseDirectory $ArchiveName
$Checksum = "$Archive.sha256"
Remove-Item -LiteralPath $Archive -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $Checksum -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $Distribution "*") -DestinationPath $Archive -CompressionLevel Optimal
$Hash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
$Utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($Checksum, "$Hash  $ArchiveName`n", $Utf8)

"Build concluído: $Executable"
"Arquivo: $Archive"
"SHA-256: $Checksum"
