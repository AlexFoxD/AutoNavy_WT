#Requires -Version 5.1

[CmdletBinding()]
param(
    [switch]$SkipCompile,
    [string]$DistributionPath,
    [string]$OutputPath,
    [string]$PyVJoyDllPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = "1"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DefaultPyVJoyDllPath = Join-Path $ProjectRoot "third_party\vjoy\2.1.9.1\x64\vJoyInterface.dll"
if (-not $PyVJoyDllPath) {
    $PyVJoyDllPath = $DefaultPyVJoyDllPath
}
if (-not (Test-Path -LiteralPath $PyVJoyDllPath -PathType Leaf)) {
    throw "pyvjoy SDK runtime DLL not found: $PyVJoyDllPath"
}
$OutputRoot = Join-Path $ProjectRoot ".output"
if (-not $OutputPath) {
    $OutputPath = Join-Path $OutputRoot "AutoNavy_WT-win64.zip"
}
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$OutputDirectory = Split-Path -Parent $OutputPath
[System.IO.Directory]::CreateDirectory($OutputDirectory) | Out-Null
$StageRoot = Join-Path $OutputDirectory "AutoNavy_WT-release-stage"
$StageRoot = [System.IO.Path]::GetFullPath($StageRoot)
if ($StageRoot -eq [System.IO.Path]::GetPathRoot($StageRoot) -or $StageRoot -eq [System.IO.Path]::GetFullPath($ProjectRoot)) {
    throw "Refusing to use an unsafe release staging path: $StageRoot"
}

if (-not $SkipCompile) {
    $Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw "Build interpreter is missing. Run scripts\install.ps1 first."
    }

    & $Python -m pip install --disable-pip-version-check -r (Join-Path $ProjectRoot "requirements-build.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install pinned build dependencies."
    }
    & $Python (Join-Path $PSScriptRoot "check_environment.py") --installation-only
    if ($LASTEXITCODE -ne 0) {
        throw "The source environment is not ready for a standalone build."
    }

    $NuitkaOutput = Join-Path $OutputRoot "nuitka"
    $env:NUITKA_CACHE_DIR = Join-Path $OutputRoot "nuitka-cache"
    if (Test-Path -LiteralPath $NuitkaOutput) {
        Remove-Item -LiteralPath $NuitkaOutput -Recurse -Force
    }
    [System.IO.Directory]::CreateDirectory($NuitkaOutput) | Out-Null

    $NuitkaArguments = @(
        "-m", "nuitka",
        "--standalone",
        "--msvc=latest",
        "--assume-yes-for-downloads",
        "--windows-console-mode=force",
        "--output-filename=AutoNavy_WT.exe",
        "--output-dir=$NuitkaOutput",
        "--include-module=start_prog",
        "--include-package=pyvjoy",
        "--include-package-data=pyvjoy",
        (Join-Path $ProjectRoot "autonavy.py")
    )
    & $Python @NuitkaArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Nuitka build failed with exit code $LASTEXITCODE."
    }

    $BuiltDistributions = @(Get-ChildItem -LiteralPath $NuitkaOutput -Directory -Filter "*.dist")
    if ($BuiltDistributions.Count -ne 1) {
        throw "Expected exactly one fresh Nuitka .dist directory; found $($BuiltDistributions.Count)."
    }
    $DistributionPath = $BuiltDistributions[0].FullName
}

if (-not $DistributionPath) {
    throw "DistributionPath is required when SkipCompile is used."
}
$DistributionPath = [System.IO.Path]::GetFullPath($DistributionPath)
if (-not (Test-Path -LiteralPath $DistributionPath -PathType Container)) {
    throw "Standalone distribution directory not found: $DistributionPath"
}

$DistributionExecutable = Join-Path $DistributionPath "AutoNavy_WT.exe"
if (-not (Test-Path -LiteralPath $DistributionExecutable -PathType Leaf)) {
    throw "Standalone executable not found: $DistributionExecutable"
}
if (-not @(Get-ChildItem -LiteralPath $DistributionPath -Recurse -File -Filter "*.dll")) {
    throw "Standalone distribution has no DLL runtime files."
}
if (-not @(Get-ChildItem -LiteralPath $DistributionPath -Recurse -File -Filter "*.pyd")) {
    throw "Standalone distribution has no PYD runtime files."
}

if (Test-Path -LiteralPath $StageRoot) {
    Remove-Item -LiteralPath $StageRoot -Recurse -Force
}
[System.IO.Directory]::CreateDirectory($StageRoot) | Out-Null

foreach ($Item in Get-ChildItem -LiteralPath $DistributionPath -Force) {
    if ($Item.Name -like "*.build" -or $Item.Name -like "*.dist" -or $Item.Name -like "*.onefile-build") {
        continue
    }
    Copy-Item -LiteralPath $Item.FullName -Destination $StageRoot -Recurse -Force
}

$PyVJoyRuntimeDirectory = Join-Path $StageRoot "pyvjoy\utils\x64"
[System.IO.Directory]::CreateDirectory($PyVJoyRuntimeDirectory) | Out-Null
Copy-Item -LiteralPath $PyVJoyDllPath -Destination (Join-Path $PyVJoyRuntimeDirectory "vJoyInterface.dll") -Force

Copy-Item -LiteralPath (Join-Path $ProjectRoot "src") -Destination (Join-Path $StageRoot "src") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "path.json") -Destination (Join-Path $StageRoot "path.json") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") -Destination (Join-Path $StageRoot "README.md") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "ЗАПУСТИТЬ.bat") -Destination (Join-Path $StageRoot "ЗАПУСТИТЬ.bat") -Force
[System.IO.Directory]::CreateDirectory((Join-Path $StageRoot "scripts")) | Out-Null
Copy-Item -LiteralPath (Join-Path $ProjectRoot "scripts\launcher.ps1") -Destination (Join-Path $StageRoot "scripts\launcher.ps1") -Force

$RequiredFiles = @(
    Get-ChildItem -LiteralPath $StageRoot -Recurse -File |
        Sort-Object FullName |
        ForEach-Object {
            $Relative = $_.FullName.Substring($StageRoot.Length + 1).Replace('\', '/')
            $Mutable = $Relative -in @("path.json", "src/origin_map.png")
            [ordered]@{ path = $Relative; size = $(if ($Mutable) { $null } else { $_.Length }) }
        }
)
$Manifest = [ordered]@{
    schema_version = 1
    launcher_version = "1.0.0"
    executable = "AutoNavy_WT.exe"
    required_files = $RequiredFiles
}
$ManifestJson = $Manifest | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText(
    (Join-Path $StageRoot "release-manifest.json"),
    $ManifestJson,
    [System.Text.UTF8Encoding]::new($false)
)

if (Test-Path -LiteralPath $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Force
}
Compress-Archive -Path (Join-Path $StageRoot "*") -DestinationPath $OutputPath -CompressionLevel Optimal
Write-Host "Release archive created: $OutputPath"
Write-Host "Release staging directory: $StageRoot"
