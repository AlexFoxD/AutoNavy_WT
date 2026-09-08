#Requires -Version 5.1

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = "1"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RepositoryRoot

if ($env:OS -ne "Windows_NT") {
    Write-Error "AutoNavy_WT поддерживает только Windows."
}

function Find-Python311 {
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        $Executable = & py.exe -3.11 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $Executable) {
            return $Executable.Trim()
        }
    }

    if (Get-Command python.exe -ErrorAction SilentlyContinue) {
        $Executable = & python.exe -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $Executable) {
            return $Executable.Trim()
        }
    }

    throw "Не найден CPython 3.11 x64. Установите его с python.org и повторите запуск."
}

$Python = Find-Python311
& $Python -c "import struct, sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) and struct.calcsize('P') == 8 else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Требуется именно 64-битный CPython 3.11 из-за модуля toolkit\way_search.cp311-win_amd64.pyd."
}

$VirtualEnvironment = Join-Path $RepositoryRoot ".venv"
$VenvPython = Join-Path $VirtualEnvironment "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    Write-Host "Создание виртуального окружения .venv..."
    & $Python -m venv $VirtualEnvironment
    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось создать виртуальное окружение."
    }
}

Write-Host "Установка зависимостей..."
& $VenvPython -m pip install --disable-pip-version-check -r (Join-Path $RepositoryRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Установка зависимостей завершилась с ошибкой."
}

Write-Host "Проверка установленной среды..."
& $VenvPython (Join-Path $PSScriptRoot "check_environment.py") --installation-only
if ($LASTEXITCODE -ne 0) {
    throw "Среда установлена не полностью. Исправьте ошибки, показанные выше."
}

Write-Host "Установка Python-зависимостей завершена."
Write-Host "Перед запуском отдельно установите драйвер vJoy, включите устройство № 1 и настройте War Thunder."
Write-Host "Запуск: .\scripts\run.ps1"
