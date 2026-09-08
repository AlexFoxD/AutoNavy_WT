#Requires -Version 5.1

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = "1"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    Write-Error "Виртуальное окружение не найдено. Сначала выполните .\scripts\install.ps1"
}

Set-Location -LiteralPath $RepositoryRoot
Write-Host "Проверка среды..."
& $Python (Join-Path $PSScriptRoot "check_environment.py")
if ($LASTEXITCODE -ne 0) {
    throw "Запуск отменён: проверка среды обнаружила ошибки."
}

Write-Host "Запуск AutoNavy_WT... Для остановки нажмите Ctrl+C."
& $Python (Join-Path $RepositoryRoot "start_prog.py")
$ApplicationExitCode = $LASTEXITCODE
if ($ApplicationExitCode -ne 0) {
    throw "AutoNavy_WT завершился с кодом ошибки $ApplicationExitCode."
}
