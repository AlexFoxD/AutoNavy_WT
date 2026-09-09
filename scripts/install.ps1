#Requires -Version 5.1
[CmdletBinding()]
param([ValidateSet('Core', 'Dev', 'Runtime', 'Build')][string]$Mode = 'Core')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$env:PYTHONUTF8 = '1'
$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root '.venv'
$Python = Join-Path $Venv 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    if (Test-Path -LiteralPath $Venv) { throw 'Existing .venv is incomplete. Inspect it manually; installer will not delete it.' }
    & py.exe -3.11 -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw 'CPython 3.11 is required to create the local environment.' }
}
& $Python -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2]==(3,11) and struct.calcsize('P')==8 else 1)"
if ($LASTEXITCODE -ne 0) { throw 'Existing .venv must be CPython 3.11 x64. Inspect it manually; no automatic deletion.' }
$Requirements = @{Core='requirements-core.txt'; Dev='requirements-dev.txt'; Runtime='requirements.txt'; Build='requirements-build.txt'}[$Mode]
& $Python -m pip install --disable-pip-version-check --cache-dir (Join-Path $Root '.output/pip-cache') -r (Join-Path $Root $Requirements)
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if ($Mode -in @('Runtime', 'Build')) {
    $Target = Join-Path $Venv 'Lib/site-packages/pyvjoy/utils/x64/vJoyInterface.dll'
    Copy-Item -LiteralPath (Join-Path $Root 'third_party/vjoy/2.1.9.1/x64/vJoyInterface.dll') -Destination $Target -Force
}
$CheckMode = if ($Mode -eq 'Dev') { 'core' } else { $Mode.ToLowerInvariant() }
& $Python (Join-Path $PSScriptRoot 'check_environment.py') --mode $CheckMode
if ($LASTEXITCODE -ne 0) { throw 'Static dependency/resource readiness failed.' }
Write-Host 'Local dependencies installed. No hardware checks or driver changes were performed.'
