[CmdletBinding()]
param(
    [string]$OutputRoot = "",
    [string]$Compiler = "",
    [string]$SigningCertificateThumbprint = "",
    [string]$SignTool = "signtool.exe",
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $OutputRoot) { $OutputRoot = Join-Path $Root "artifacts" }
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
$Payload = Join-Path $OutputRoot "SortInator"
$Manifest = Get-Content -LiteralPath (Join-Path $Payload "update-manifest.json") -Raw | ConvertFrom-Json
$Version = $Manifest.version
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid package version" }
if (-not $Compiler) {
    $Candidates = @(
        (Join-Path $Root "artifacts\tools\InnoSetup\ISCC.exe"),
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 7\ISCC.exe"
    )
    $Compiler = $Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $Compiler -or -not (Test-Path -LiteralPath $Compiler)) {
    throw "Inno Setup compiler missing. Run scripts\setup_installer.ps1 or supply -Compiler."
}
$Releases = Join-Path $OutputRoot "releases"
New-Item -ItemType Directory -Path $Releases -Force | Out-Null
$Arguments = @("/DAppVersion=$Version", "/DPayloadDir=$Payload", "/DOutputDir=$Releases")
if ($SigningCertificateThumbprint) {
    if ($SigningCertificateThumbprint -notmatch '^[0-9a-fA-F]{40}$') { throw "Invalid signing thumbprint" }
    $Signature = Get-AuthenticodeSignature -LiteralPath (Join-Path $Payload "SortInator.exe")
    if ($Signature.Status -ne "Valid") { throw "Sign the application before building a signed installer" }
    $Arguments += "/DSignedBuild=1"
    $Arguments += '/Sorganizador=$q' + $SignTool + '$q sign /sha1 ' + $SigningCertificateThumbprint + ' /fd SHA256 /tr $q' + $TimestampUrl + '$q /td SHA256 $f'
}
& $Compiler @Arguments (Join-Path $PSScriptRoot "installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed" }
$Installer = Join-Path $Releases "SortInator-$Version-Setup.exe"
if ($SigningCertificateThumbprint -and (Get-AuthenticodeSignature -LiteralPath $Installer).Status -ne "Valid") {
    throw "Installer signature verification failed"
}
$Hash = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText("$Installer.sha256", "$Hash  $([IO.Path]::GetFileName($Installer))`n", [Text.UTF8Encoding]::new($false))
Write-Output "Installer: $Installer"
if (-not $SigningCertificateThumbprint) { Write-Output "Unsigned candidate: Windows reputation warnings may still appear." }
