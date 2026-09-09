#Requires -Version 5.1
# Preserve every CLI argument, including flags unknown to PowerShell.
param()
& (Join-Path $PSScriptRoot "launcher.ps1") @args
exit $LASTEXITCODE
