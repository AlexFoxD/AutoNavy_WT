#Requires -Version 5.1

[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = "1"

$Arguments = @()
if ($CheckOnly) { $Arguments += "-CheckOnly" }
if ($NoPause) { $Arguments += "-NoPause" }
& (Join-Path $PSScriptRoot "launcher.ps1") @Arguments
exit $LASTEXITCODE
